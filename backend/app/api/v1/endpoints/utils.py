
from fastapi import APIRouter, Query, HTTPException
import httpx
from bs4 import BeautifulSoup
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/link-preview")
async def get_link_preview(url: str = Query(..., description="The URL to preview")):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, follow_redirects=True)
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Could not fetch URL")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            title = None
            if soup.find("meta", property="og:title"):
                title = soup.find("meta", property="og:title")["content"]
            elif soup.title:
                title = soup.title.string

            description = None
            if soup.find("meta", property="og:description"):
                description = soup.find("meta", property="og:description")["content"]
            elif soup.find("meta", attrs={"name": "description"}):
                description = soup.find("meta", attrs={"name": "description"})["content"]

            image = None
            if soup.find("meta", property="og:image"):
                image = soup.find("meta", property="og:image")["content"]

            return {
                "title": title,
                "description": description,
                "image": image,
                "url": url
            }
    except Exception as e:
        logger.error(f"Error fetching link preview for {url}: {e}")
        return {"error": str(e)}
