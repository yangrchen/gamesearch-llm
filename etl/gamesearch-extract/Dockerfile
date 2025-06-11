FROM golang:1.24.1-alpine AS build

WORKDIR /app

COPY go.mod go.sum ./

RUN go mod download

COPY main.go .

RUN GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -tags lambda.norpc -o main main.go

FROM public.ecr.aws/lambda/provided:al2023

COPY --from=build /app/main ./main

ENTRYPOINT ["./main"]
