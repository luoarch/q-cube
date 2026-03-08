import uvicorn


def main() -> None:
    uvicorn.run("q3_ai_assistant.main:app", host="0.0.0.0", port=8400)


if __name__ == "__main__":
    main()
