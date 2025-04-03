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

	"github.com/aws/aws-lambda-go/lambda"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	log "github.com/sirupsen/logrus"
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
	logger      *log.Logger
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
		return nil, fmt.Errorf("Error decoding API response: %v", err)
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

var s3Client *s3.Client

func init() {
	cfg, err := config.LoadDefaultConfig(context.TODO())
	if err != nil {
		log.Fatalf("Unable to load SDK config, %v", err)
	}

	s3Client = s3.NewFromConfig(cfg)
}

func uploadToS3(ctx context.Context, key string, data []byte) error {
	bucketName := os.Getenv("S3_BUCKET")
	if bucketName == "" {
		return fmt.Errorf("S3_BUCKET variable is required but not set")
	}
	_, err := s3Client.PutObject(ctx, &s3.PutObjectInput{
		Bucket: &bucketName,
		Key:    &key,
		Body:   bytes.NewReader(data),
	})

	if err != nil {
		return fmt.Errorf("Failed to upload data to S3: %v", err)
	}

	return nil
}

func fetchAndStoreData(ctx context.Context, logger *log.Logger) error {

	clientID := os.Getenv("CLIENT_ID")
	clientSecret := os.Getenv("CLIENT_SECRET")

	if clientID == "" || clientSecret == "" {
		return fmt.Errorf("CLIENT_ID or CLIENT_SECRET variables are required but not set")
	}

	authResp, err := retrieveAuthToken(clientID, clientSecret)
	if err != nil {
		log.Errorf("Error retrieving authentication token: %v", err)
		return err
	}

	// IGDB has a request rate limit of 4 req / sec
	limiter := rate.NewLimiter(4, 1)
	numWorkers := 3
	pageLimit := 500

	genresFetcher := Fetcher[Genre]{
		clientID:    clientID,
		accessToken: authResp.AccessToken,
		url:         "https://api.igdb.com/v4/genres",
		limiter:     limiter,
		ctx:         ctx,
		logger:      logger,
	}
	genresQuery := "fields id, name;"

	genres := genresFetcher.fetchAll(genresQuery, numWorkers, pageLimit)

	gamesFetcher := Fetcher[Game]{
		clientID:    clientID,
		accessToken: authResp.AccessToken,
		url:         "https://api.igdb.com/v4/games",
		limiter:     limiter,
		ctx:         ctx,
		logger:      logger,
	}
	gamesQuery := "fields id, name, first_release_date, dlcs, franchises, genres, multiplayer_modes, ports, summary;"

	games := gamesFetcher.fetchAll(gamesQuery, numWorkers, pageLimit)

	franchisesFetcher := Fetcher[Franchise]{
		clientID:    clientID,
		accessToken: authResp.AccessToken,
		url:         "https://api.igdb.com/v4/franchises",
		limiter:     limiter,
		ctx:         ctx,
		logger:      logger,
	}
	franchisesQuery := "fields id, name, games;"
	franchises := franchisesFetcher.fetchAll(franchisesQuery, numWorkers, pageLimit)

	fileMap := map[string]any{
		"games.json":      games,
		"genres.json":     genres,
		"franchises.json": franchises,
	}

	for filename, value := range fileMap {
		data, err := json.MarshalIndent(value, "", "  ")
		if err != nil {
			logger.Errorf("Error marshaling JSON for %s: %v", filename, err)
			continue
		}

		if err := uploadToS3(ctx, filename, data); err != nil {
			logger.Errorf("Error uploading %s to S3: %v", filename, err)
		}
	}

	return nil

}

func handleRequest(ctx context.Context, event json.RawMessage) error {
	logger := log.New()
	logger.SetFormatter(&log.JSONFormatter{})

	if err := fetchAndStoreData(ctx, logger); err != nil {
		return err
	}
	return nil

}

func main() {
	ctx := context.Background()

	if os.Getenv("AWS_LAMBDA_FUNCTION_NAME") != "" {
		lambda.Start(handleRequest)
		return
	}

	logger := log.New()
	logger.SetFormatter(&log.JSONFormatter{})

	if err := fetchAndStoreData(ctx, logger); err != nil {
		logger.Fatalf("Error executing data fetch: %v", err)
	}
}
