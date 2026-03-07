import uvicorn


def main() -> None:
    uvicorn.run("q3_market_ingestion.main:app", host="0.0.0.0", port=8200)


if __name__ == "__main__":
    main()
