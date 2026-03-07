import uvicorn


def main() -> None:
    uvicorn.run("q3_quant_engine.main:app", host="0.0.0.0", port=8100)


if __name__ == "__main__":
    main()
