package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/joho/godotenv"
	"github.com/sirupsen/logrus"
	"golang.org/x/time/rate"
)

type AuthTokenResponse struct {
	AccessToken string `json:"access_token"`
	ExpiresIn   int    `json:"expires_in"`
	TokenType   string `json:"string"`
}

type Game struct {
	ID                int    `json:"id"`
	Name              string `json:"name"`
	FirstReleaseDate  int    `json:"first_release_date"`
	DLCID             []int  `json:"dlcs"`
	FranchiseID       []int  `json:"franchises"`
	GenreID           []int  `json:"genres"`
	MultiplayerModeID []int  `json:"multiplayer_modes"`
	PortID            []int  `json:"ports"`
	Summary           string `json:"summary"`
}

type Genre struct {
}

type Fetcher[T Game | Genre] struct {
	clientID    string
	accessToken string
	url         string
	limiter     *rate.Limiter
	ctx         context.Context
	logger      *logrus.Logger
}

func (f *Fetcher[T]) fetchQuery(query string) ([]T, error) {

	req, err := http.NewRequest(http.MethodPost, f.url, bytes.NewBuffer([]byte(query)))
	if err != nil {
		return nil, err
	}

	req.Header.Set("Client-ID", f.clientID)
	req.Header.Set("Authorization", "Bearer "+f.accessToken)
	req.Header.Set("Content-Type", "text/plain")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API returned status code %d: %s", resp.StatusCode, string(body))
	}

	var respStruct []T
	if err := json.NewDecoder(resp.Body).Decode(&respStruct); err != nil {
		return nil, fmt.Errorf("Error decoding API response: %s", err)
	}

	return respStruct, nil
}

func (f *Fetcher[T]) fetchAll(query string, numWorkers, pageLimit int) []T {
	var wg sync.WaitGroup
	offsetChan := make(chan int, 5)
	resultChan := make(chan []T)

	var results []T

	for i := range numWorkers {
		offsetChan <- pageLimit * i
	}

	for i := range numWorkers {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			for offset := range offsetChan {
				f.limiter.Wait(f.ctx)

				var builder strings.Builder
				builder.WriteString(query)
				builder.WriteString(fmt.Sprintf("\nlimit %d;\noffset %d;", pageLimit, offset))

				res, err := f.fetchQuery(builder.String())
				if err != nil {
					f.logger.Errorf("Error fetching results with offset %d: %v\n", offset, err)
					continue
				}

				resultChan <- res

				f.logger.Infof("Queried results at offset %d, worker %d, at time %s\n", offset, i, time.Now().String())

				if len(res) < pageLimit {
					f.logger.Infof("Worker %d finished - received partial results (%d < %d)\n", i, len(res), pageLimit)
					return
				}

				offsetChan <- offset + pageLimit*numWorkers
			}
		}(i)
	}

	go func() {
		wg.Wait()
		f.logger.Info("All workers finished.")
		close(offsetChan)
		close(resultChan)
	}()

	for r := range resultChan {
		results = append(results, r...)
	}

	return results
}

func retrieveAuthToken(clientID, clientSecret string) (*AuthTokenResponse, error) {
	authResp := new(AuthTokenResponse)
	res, err := http.Post(fmt.Sprintf("https://id.twitch.tv/oauth2/token?client_id=%s&client_secret=%s&grant_type=client_credentials", clientID, clientSecret), "application/json", nil)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()

	if err := json.NewDecoder(res.Body).Decode(&authResp); err != nil {
		return nil, err
	}

	return authResp, nil
}

// func fetchQuery[T Game | Genre](query, clientID, accessToken, url string) ([]T, error) {
// 	req, err := http.NewRequest(http.MethodPost, url, bytes.NewBuffer([]byte(query)))
// 	if err != nil {
// 		return nil, err
// 	}

// 	req.Header.Set("Client-ID", clientID)
// 	req.Header.Set("Authorization", "Bearer "+accessToken)
// 	req.Header.Set("Content-Type", "text/plain")

// 	client := &http.Client{}
// 	resp, err := client.Do(req)
// 	if err != nil {
// 		return nil, err
// 	}
// 	defer resp.Body.Close()

// 	if resp.StatusCode != http.StatusOK {
// 		body, _ := io.ReadAll(resp.Body)
// 		return nil, fmt.Errorf("API returned status code %d: %s", resp.StatusCode, string(body))
// 	}

// 	var respStruct []T
// 	if err := json.NewDecoder(resp.Body).Decode(&respStruct); err != nil {
// 		return nil, fmt.Errorf("Error decoding API response: %s", err)
// 	}

// 	return respStruct, nil
// }

// func fetchGames(query, clientID, accessToken string) ([]Game, error) {
// 	url := "https://api.igdb.com/v4/games"
// 	req, err := http.NewRequest(http.MethodPost, url, bytes.NewBuffer([]byte(query)))
// 	if err != nil {
// 		return nil, err
// 	}

// 	req.Header.Set("Client-ID", clientID)
// 	req.Header.Set("Authorization", "Bearer "+accessToken)
// 	req.Header.Set("Content-Type", "text/plain")

// 	client := &http.Client{}
// 	resp, err := client.Do(req)
// 	if err != nil {
// 		return nil, err
// 	}
// 	defer resp.Body.Close()

// 	if resp.StatusCode != http.StatusOK {
// 		body, _ := io.ReadAll(resp.Body)
// 		return nil, fmt.Errorf("API returned status code %d: %s", resp.StatusCode, string(body))
// 	}

// 	var games []Game
// 	if err := json.NewDecoder(resp.Body).Decode(&games); err != nil {
// 		return nil, fmt.Errorf("Error decoding API response: %s", err)
// 	}

// 	return games, nil
// }

func main() {

	ctx := context.Background()
	log := logrus.New()

	if err := godotenv.Load(); err != nil {
		log.Fatal("Error loading .env file")
	}

	clientID := os.Getenv("CLIENT_ID")
	clientSecret := os.Getenv("CLIENT_SECRET")

	authResp, err := retrieveAuthToken(clientID, clientSecret)
	if err != nil {
		log.Errorf("Error retrieving authentication token: %s", err)
		log.Exit(1)
	}

	limiter := rate.NewLimiter(4, 1)
	numWorkers := 3
	pageLimit := 500

	gamesFetcher := Fetcher[Game]{
		clientID:    clientID,
		accessToken: authResp.AccessToken,
		url:         "https://api.igdb.com/v4/games",
		limiter:     limiter,
		ctx:         ctx,
		logger:      log,
	}
	gamesQuery := "fields name, first_release_date, dlcs, franchises, genres, multiplayer_modes, ports, summary;"

	gamesFetcher.fetchAll(gamesQuery, numWorkers, pageLimit)

	// offsetChan := make(chan int, 5)
	// gameResults := make(chan []Game)

	// var allGames []Game
	// for i := range numWorkers {
	// 	offsetChan <- pageLimit * i
	// }

	// for i := range numWorkers {
	// 	wgGames.Add(1)
	// 	go func(i int) {
	// 		defer wgGames.Done()
	// 		for offset := range offsetChan {
	// 			limiter.Wait(ctx)
	// 			query := fmt.Sprintf(`
	// 				fields name, first_release_date, dlcs, franchises, genres, multiplayer_modes, ports, summary;
	// 				limit %d;
	// 				offset %d;
	// 			`, pageLimit, offset)

	// 			games, err := fetchQuery(query, clientID, authResp.AccessToken)
	// 			if err != nil {
	// 				log.Errorf("Error fetching games with offset %d: %v\n", offset, err)
	// 				continue
	// 			}

	// 			gameResults <- games

	// 			log.Infof("Queried games at offset %d, worker %d, at time %s\n", offset, i, time.Now().String())

	// 			if len(games) < pageLimit {
	// 				log.Infof("Worker %d finished - received partial results (%d < %d)\n", i, len(games), pageLimit)
	// 				return
	// 			}

	// 			offsetChan <- offset + pageLimit*numWorkers
	// 		}
	// 	}(i)
	// }

	// go func() {
	// 	wgGames.Wait()
	// 	log.Info("All workers finished.")
	// 	close(offsetChan)
	// 	close(gameResults)
	// }()

	// file, err := os.Create("games.json")
	// if err != nil {
	// 	log.Errorf("Error creating file: %s", err)
	// 	return
	// }
	// defer file.Close()

	// for r := range gameResults {
	// 	allGames = append(allGames, r...)
	// }

	// encoder := json.NewEncoder(file)
	// encoder.SetIndent("", "  ")

	// if err := encoder.Encode(allGames); err != nil {
	// 	log.Errorf("Error encoding games to JSON: %s", err)
	// 	return
	// }

}
