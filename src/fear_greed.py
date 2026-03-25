import requests

def fetch_fear_greed_index():
    """
    Fetch the Fear/Greed index from alternative.me.
    """
    url = "https://api.alternative.me/fng/"
    try:
        response = requests.get(url)
        data = response.json()
        if data['metadata']['error'] is None:
            return data['data'][0]
        return None
    except Exception as e:
        print(f"Error fetching Fear/Greed index: {e}")
        return None
