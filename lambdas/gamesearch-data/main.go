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
	ID               int    `json:"id"`
	Name             string `json:"name"`
	FirstReleaseDate int    `json:"first_release_date"`
	Franchises       []int  `json:"franchises"`
	Genres           []int  `json:"genres"`
	Summary          string `json:"summary"`
	// DLC            []int  `json:"dlcs"`
	// MultiplayerModes []int  `json:"multiplayer_modes"`
	// Ports            []int  `json:"ports"`
}

type Genre struct {
	ID   int    `json:"id"`
	Name string `json:"name"`
}

type Franchise struct {
	ID    int    `json:"id"`
	Name  string `json:"name"`
	Games []int  `json:"games"`
}

type Fetcher[T Game | Genre | Franchise] struct {
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

	var results []T
	if err := json.NewDecoder(resp.Body).Decode(&results); err != nil {
		return nil, fmt.Errorf("Error decoding API response: %s", err)
	}

	return results, nil
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

func writeJSON(objects any, filepath string, logger *logrus.Logger) error {
	file, err := os.Create(filepath)
	if err != nil {
		return fmt.Errorf("Error creating file: %s", err)
	}
	defer file.Close()

	encoder := json.NewEncoder(file)
	encoder.SetIndent("", "  ")

	if err := encoder.Encode(objects); err != nil {
		return fmt.Errorf("Error writing objects to JSON: %s", err)
	}

	logger.Infof("Wrote JSON file at: %s", filepath)
	return nil
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

	genresFetcher := Fetcher[Genre]{
		clientID:    clientID,
		accessToken: authResp.AccessToken,
		url:         "https://api.igdb.com/v4/genres",
		limiter:     limiter,
		ctx:         ctx,
		logger:      log,
	}
	genresQuery := "fields id, name;"

	genres := genresFetcher.fetchAll(genresQuery, numWorkers, pageLimit)

	gamesFetcher := Fetcher[Game]{
		clientID:    clientID,
		accessToken: authResp.AccessToken,
		url:         "https://api.igdb.com/v4/games",
		limiter:     limiter,
		ctx:         ctx,
		logger:      log,
	}
	gamesQuery := "fields id, name, first_release_date, dlcs, franchises, genres, multiplayer_modes, ports, summary;"

	games := gamesFetcher.fetchAll(gamesQuery, numWorkers, pageLimit)

	franchisesFetcher := Fetcher[Franchise]{
		clientID:    clientID,
		accessToken: authResp.AccessToken,
		url:         "https://api.igdb.com/v4/franchises",
		limiter:     limiter,
		ctx:         ctx,
		logger:      log,
	}
	franchisesQuery := "fields id, name, games;"
	franchises := franchisesFetcher.fetchAll(franchisesQuery, numWorkers, pageLimit)

	var wgFile sync.WaitGroup
	fileMap := map[string]any{
		"games.json":      games,
		"genres.json":     genres,
		"franchises.json": franchises,
	}

	for filename, value := range fileMap {
		wgFile.Add(1)
		go func() {
			defer wgFile.Done()
			writeJSON(value, filename, log)
		}()
	}

	wgFile.Wait()
}
