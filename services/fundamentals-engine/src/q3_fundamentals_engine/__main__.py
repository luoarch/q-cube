import uvicorn


def main() -> None:
    uvicorn.run("q3_fundamentals_engine.main:app", host="0.0.0.0", port=8300)


if __name__ == "__main__":
    main()
