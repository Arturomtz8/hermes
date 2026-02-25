import httpx

def test_stream():
    url = "http://localhost:8000/process"
    params = {"url": "https://www.youtube.com/watch?v=ZNFBucUhEYU"}
    
    # We use a context manager to keep the connection open
    with httpx.stream("GET", url, params=params, timeout=None) as r:
        for line in r.iter_lines():
            if line.startswith("data: "):
                print(f"Update: {line[6:]}")

if __name__ == "__main__":
    test_stream()
