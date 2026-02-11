import requests
from bs4 import BeautifulSoup
import json
import os
import tweepy
import argparse
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import boto3
from botocore.exceptions import ClientError
from scripts import config
# --- Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Environment Variables & AWS/S3 ---
is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
s3_bucket_name = "stilesdata.com"

if is_github_actions:
    session = boto3.Session(
        region_name="us-west-1"
    )
else:
    profile_name = os.environ.get("AWS_PERSONAL_PROFILE", "haekeo")
    session = boto3.Session(profile_name=profile_name, region_name="us-west-1")

s3_resource = session.resource("s3")

def get_last_tweet_date(tweet_type):
    """Reads the last tweet date for a given type from S3."""
    s3_key = f"redsox/data/tweets/last_tweet_date_{tweet_type}.txt"
    try:
        obj = s3_resource.Object(s3_bucket_name, s3_key)
        last_date_str = obj.get()['Body'].read().decode('utf-8').strip()
        return last_date_str
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise

def set_last_tweet_date(date_str, tweet_type):
    """Writes the last tweet date for a given type to S3."""
    s3_key = f"redsox/data/tweets/last_tweet_date_{tweet_type}.txt"
    obj = s3_resource.Object(s3_bucket_name, s3_key)
    obj.put(Body=date_str)
    logging.info(f"Successfully updated last tweet date for '{tweet_type}' to: {date_str}")

def post_tweet(tweet_text, tweet_type):
    """Posts a tweet and updates the last tweet date on success."""
    TEAM_TWITTER_API_KEY = os.environ.get("TEAM_TWITTER_API_KEY")
    TEAM_TWITTER_API_SECRET = os.environ.get("TEAM_TWITTER_API_SECRET")
    TEAM_TWITTER_TOKEN = os.environ.get("TEAM_TWITTER_TOKEN")
    TEAM_TWITTER_TOKEN_SECRET = os.environ.get("TEAM_TWITTER_TOKEN_SECRET")
    
    if not all([TEAM_TWITTER_API_KEY, TEAM_TWITTER_API_SECRET, TEAM_TWITTER_TOKEN, TEAM_TWITTER_TOKEN_SECRET]):
        logging.error("Twitter API credentials are not fully set. Cannot post tweet.")
        return

    try:
        client = tweepy.Client(
            consumer_key=TEAM_TWITTER_API_KEY,
            consumer_secret=TEAM_TWITTER_API_SECRET,
            access_token=TEAM_TWITTER_TOKEN,
            access_token_secret=TEAM_TWITTER_TOKEN_SECRET
        )
        response = client.create_tweet(text=tweet_text)
        logging.info(f"Tweet posted successfully: {response.data['id']}")
        team_tz = ZoneInfo(config.TEAM_TIMEZONE)
        today_str = datetime.now(team_tz).strftime('%Y-%m-%d')
        set_last_tweet_date(today_str, tweet_type)
    except Exception as e:
        logging.error(f"Failed to post tweet: {e}")

# TODO: Add Boston Globe and other Red Sox-specific news sources.
# TODO: Add Boston Globe or other Red Sox specific sources.

def fetch_mlb_news():
    """
    Fetches the top story from MLB.com.
    """
    url = f"https://www.mlb.com/{config.TEAM_NAME.replace(' ', '').lower()}/news"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the URL: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the first article item
    article_item = soup.find('li', class_='article-navigation__item')

    if not article_item:
        print("Could not find the main story on MLB.com.")
        return None

    story_data = {}

    # Extract title and URL
    headline_tag = article_item.find('span', class_='article-navigation__item__meta-headline')
    link_tag = article_item.find('a')

    if headline_tag:
        story_data['title'] = headline_tag.get_text(strip=True)
    else:
        story_data['title'] = None

    if link_tag and link_tag.has_attr('href'):
        story_data['url'] = f"https://www.mlb.com{link_tag['href']}"
    else:
        story_data['url'] = None

    # Description and time are not available in the list view
    story_data['description'] = None
    story_data['time'] = None

    story_data['source'] = 'MLB.com'
    return story_data

def format_news_tweet(articles):
    """Formats a list of articles into a tweet."""
    tweet_lines = []
    for article in articles:
        if article and article.get('title') and article.get('url'):
            tweet_lines.append(f"- {article['source']}: {article['title']} {article['url']}")
    return "\n\n".join(tweet_lines)

def should_post_news():
    """Determines if news should be posted based on time and whether it's been posted today."""
    team_tz = ZoneInfo(config.TEAM_TIMEZONE)
    current_hour = datetime.now(team_tz).hour
    today_str = datetime.now(team_tz).strftime('%Y-%m-%d')
    
    # Check if already posted today
    last_tweet_date = get_last_tweet_date("news")
    if last_tweet_date == today_str:
        logging.info("News has already been posted today. Skipping.")
        return False
    
    # Post news during reasonable hours (8 AM to 6 PM PT)
    if 8 <= current_hour <= 18:
        logging.info(f"Good time to post news (hour: {current_hour})")
        return True
    else:
        logging.info(f"Outside prime news hours (hour: {current_hour}). Skipping news post.")
        return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Fetch Red Sox news and optionally post to Twitter.")
    parser.add_argument("--post-tweet", action="store_true", help="Post the news roundup to Twitter.")
    parser.add_argument("--force", action="store_true", help="Force posting regardless of time (still respects daily limit).")
    args = parser.parse_args()

    tweet_type = "news"
    team_tz = ZoneInfo(config.TEAM_TIMEZONE)
    today_str = datetime.now(team_tz).strftime('%Y-%m-%d')

    # Check if we should post (unless forced)
    if not args.force and not should_post_news():
        exit()

    articles = []
    
    # latimes_news = fetch_latimes_news()
    # if latimes_news:
    #     articles.append(latimes_news)

    # dodgers_nation_news = fetch_dodgers_nation_news()
    # if dodgers_nation_news:
    #     articles.append(dodgers_nation_news)
    
    mlb_news = fetch_mlb_news()
    if mlb_news:
        articles.append(mlb_news)

    if articles:
        tweet_text = format_news_tweet(articles)
        print("--- Generated Tweet ---")
        print(tweet_text)

        if args.post_tweet:
            post_tweet(tweet_text, tweet_type)
        else:
            logging.info("Dry run: --post-tweet flag not provided. Not posting to Twitter.")
    else:
        logging.info("No articles found to tweet.") 