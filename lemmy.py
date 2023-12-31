from youtubesearchpython import *
from datetime import datetime
from pythorhead import Lemmy
import langdetect
import yaml
import os
import sys


def read_config():

    app_root_path = os.path.dirname(os.path.realpath(__file__))

    config_path = os.path.join(app_root_path, 'configs')
    config_filepath = os.path.join(config_path, 'config.yml')

    with open(config_filepath, "r") as config_file:
        config_yaml_load = yaml.safe_load(config_file)

    return config_yaml_load


def login_to_lemmy():

    lemmy_instance = Lemmy(lemmy_instance_url)
    lemmy_instance.log_in(lemmy_username, lemmy_password)
    lemmy_instance_community_id = lemmy_instance.discover_community(community_name)

    return lemmy_instance, lemmy_instance_community_id


def search_lemmy_posts(youtube_video_title, youtube_video_url):

    page_number_int = 1
    lemmy_search_post_name_list = []
    lemmy_search_post_url_list = []

    # loop over pages until the result is empty
    while True:

        # search lemmy for existing posts
        lemmy_search_result = lemmy.post.list(community_id=community_id, community_name=community_name, page=page_number_int)

        if not lemmy_search_result:
            break

        # get post names and append to list
        for i in lemmy_search_result:

            lemmy_search_post_name = (i['post']['name'])
            lemmy_search_post_name_list.append(lemmy_search_post_name)

            try:

                lemmy_search_post_url = (i['post']['url'])
                lemmy_search_post_url_list.append(lemmy_search_post_url)

            except KeyError:

                continue

        # increment page number
        page_number_int += 1

    if youtube_video_url in lemmy_search_post_url_list:
        print(f"[SKIP] YouTube URL '{youtube_video_url}' found in existing Lemmy post, skipping post...")
        return False

    if youtube_video_title in lemmy_search_post_name_list:
        print(f"[SKIP] YouTube title '{youtube_video_title}' found in existing Lemmy post, skipping post...")
        return False

    return True


def post_to_lemmy(youtube_video_title, youtube_video_link):

    print(f"[SUCCESS] YouTube title '{youtube_video_title}' passed, posting to Lemmy...")
    lemmy.post.create(community_id, name=youtube_video_title, body=f"Automated post: UNRAID related video posted on YouTube '{youtube_video_title}'", url=youtube_video_link)


def youtube_duration_detect(youtube_video_title, youtube_video_duration):

    try:
        youtube_duration_time_object = datetime.strptime(youtube_video_duration, '%H:%M:%S').time()
    except ValueError:
        try:
            youtube_duration_time_object = datetime.strptime(youtube_video_duration, '%M:%S').time()
        except ValueError:
            try:
                youtube_duration_time_object = datetime.strptime(youtube_video_duration, '%S').time()
            except ValueError:
                print(f"[ERROR] Unable to determine datetime from YouTube duration string '{youtube_video_duration}', exiting script...")
                sys.exit(3)

    youtube_min_duration_time_object = datetime.strptime(youtube_min_duration, '%M:%S').time()

    if youtube_duration_time_object < youtube_min_duration_time_object:
        print(f"[SKIP] Duration length '{youtube_video_duration}' for YouTube title '{youtube_video_title}' is less than minimum value '{youtube_min_duration}', skipping post...")
        return False

    return True


def youtube_language_detect(youtube_video_title):

    try:

        detect_language_code = langdetect.detect(youtube_video_title)

    except langdetect.lang_detect_exception.LangDetectException:

        print(f"[SKIP] Language code not detectable for YouTube title '{youtube_video_title}', skipping post...")
        return False

    if detect_language_code != 'en':
        print(f"[SKIP] Language code '{detect_language_code}' for YouTube title '{youtube_video_title}' is not english, skipping post...")
        return False

    # TODO try and get comments or description from video and analyse for lang as well
    if not youtube_video_title.isascii():
        print(f"[SKIP] Non ASCII characters detected for YouTube title '{youtube_video_title}', skipping post...")
        return False

    return True


# noinspection PyTypeChecker
def youtube_channel_search(channel_name_list):

    for channel_name in channel_name_list:

        # get channel id for youtube unraid specific channels
        youtube_channels_search = ChannelsSearch(channel_name, limit=1, region='US')

        # print(youtube_channels_search.result())
        youtube_channels_search_result = youtube_channels_search.result()

        # grab the channel details, note grabbing first channel only
        channel_id = youtube_channels_search_result['result'][0]['id']
        # channel_title = youtube_channels_search_result['result'][0]['title']

        if not channel_id:
            continue

        playlist = Playlist(playlist_from_channel_id(channel_id))

        # grab the video details, note grabbing first video only
        youtube_video_duration = playlist.videos[0]['duration']
        youtube_video_title = playlist.videos[0]['title']
        youtube_video_link = playlist.videos[0]['link']

        if not youtube_duration_detect(youtube_video_title, youtube_video_duration):
            continue

        if not youtube_language_detect(youtube_video_title):
            continue

        if not search_lemmy_posts(youtube_video_title, youtube_video_link):
            continue

        post_to_lemmy(youtube_video_title, youtube_video_link)


# noinspection PyTypeChecker
def youtube_video_search():

    # search YouTube for videos titles with keyword defined in youtube_query
    custom_search_result = CustomSearch(youtube_query, VideoSortOrder.uploadDate, limit=youtube_query_result_limit, language=youtube_query_language)
    youtube_results = custom_search_result.result()

    # loop over YouTube results
    for youtube_result in youtube_results['result']:

        youtube_video_title = youtube_result['title']
        youtube_video_duration = youtube_result['duration']
        youtube_video_link = youtube_result['link']

        # if youtube title does not contain query then skip
        if youtube_query.lower() not in youtube_video_title.lower():
            print(f"[SKIP] YouTube video title '{youtube_video_title}' does not contain query string '{youtube_query}'")
            continue

        # if duration of youtube video is less than defined value then skip
        if not youtube_duration_detect(youtube_video_title, youtube_video_duration):
            continue

        # if language of youtube title does not match defined value then skip
        if not youtube_language_detect(youtube_video_title):
            continue

        # if lemmy post title and/or youtube link already exist then skip
        if not search_lemmy_posts(youtube_video_title, youtube_video_link):
            continue

        # if all checks passed then post to lemmy
        post_to_lemmy(youtube_video_title, youtube_video_link)


# required to prevent separate process from trying to load parent process
if __name__ == '__main__':

    # get credentials from env var secrets
    lemmy_username = os.getenv('LEMMY_USERNAME', '')
    lemmy_password = os.getenv('LEMMY_PASSWORD', '')

    if not lemmy_username:
        print(f"[ERROR] Lemmy username is not specified via env var 'LEMMY_USERNAME', exiting script...")
        sys.exit(1)

    if not lemmy_password:
        print(f"[ERROR] Lemmy password is not specified via env var 'LEMMY_PASSWORD', exiting script...")
        sys.exit(2)

    # read in config file
    config_yaml = read_config()

    # get lemmy config
    community_name = config_yaml["lemmy"]['community_name']
    lemmy_instance_url = config_yaml["lemmy"]['lemmy_instance']

    # get youtube config
    youtube_query = config_yaml["youtube"]['youtube_query']
    youtube_query_result_limit = config_yaml["youtube"]['youtube_query_result_limit']
    youtube_query_language = config_yaml["youtube"]['youtube_query_language']
    youtube_min_duration = config_yaml["youtube"]['youtube_min_duration']
    youtube_channel_search_list = config_yaml["youtube"]['youtube_channel_search']

    # login to lemmy
    lemmy, community_id = login_to_lemmy()

    # define youtube channels that provide unraid content
    youtube_channel_search(youtube_channel_search_list)

    # search for YouTube videos related to unraid
    youtube_video_search()
