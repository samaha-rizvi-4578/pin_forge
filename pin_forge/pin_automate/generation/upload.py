import requests

PINTEREST_ACCESS_TOKEN = ""
PINTEREST_BOARD_ID = "YOUR_BOARD_ID"

def upload_pin(title, alt_text, image_url):
    url = "https://api.pinterest.com/v5/pins"
    
    headers = {
        "Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "title": title,
        "alt_text": alt_text,
        "board_id": PINTEREST_BOARD_ID,
        "media_source": {
            "source_type": "image_url",
            "url": image_url
        }
    }

    resp = requests.post(url, json=data, headers=headers)
    return resp.json()


