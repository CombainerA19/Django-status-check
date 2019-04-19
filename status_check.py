import time

import requests
import bs4
import praw
import gspread

from oauth2client.service_account import ServiceAccountCredentials
from helper import is_processing_row

class RedditDjangoPublication():
    def __init__(self):
        self.destination_page = "http://134.209.15.93:8000/admin/reddit_bot/post/"
        self.login_page = "http://134.209.15.93:8000/admin/login/"
        self.new_order = "http://134.209.15.93:8000/admin/reddit_bot/order/add/"

        self._session = None
        self.destination_page_content = None
        self.destination_page_table_index = 0
        self.destination_page_current_table_index_url = ""
        self.destination_page_table_length = None
        self.active_destination_page_url = None
        self.csrfmiddlewaretoken = ""
        self.active_subreddit_name = ""

        self.reddit = praw.Reddit("bot2")
        self.sub = self.reddit.subreddit("all")

        self.scope = ["https://spreadsheets.google.com/feeds",
                      "https://www.googleapis.com/auth/drive"]
        self.creds = ServiceAccountCredentials.from_json_keyfile_name("Document Editing Rescan-7d7d0fac1720.json", self.scope)
        self.client = gspread.authorize(self.creds)

    def init_session(self):
        with requests.Session() as session:
            req = session.get(self.login_page)
            token = self.extract_csrftoken(req)

            payload = {
                "csrfmiddlewaretoken" : f"{token}",
                "next" : "/admin/reddit_bot/post/",
                "password"	: "FQUFZV55zaV886eNbdaYTTs87T5Ji",
                "username" : "orders"
            }

            self.csrfmiddlewaretoken = token
            session.post(self.login_page, data=payload)
            self._session = session

    def extract_csrftoken(self, page):
        soup = bs4.BeautifulSoup(page.text, features="html.parser")
        return soup.select("input[type='hidden']")[0].get("value")

    def show_states(self):
        return self._session, self.csrfmiddlewaretoken

    def working_session(self):
        with self._session as session:
            req = session.get(self.destination_page)
            self.destination_page_content = req

    def recurs_till_end(self):
        self.extract_url_from_row()
        if self.destination_page_current_table_index_url != "":
            self.process_index_url()
        if self.destination_page_table_length != None:
            length = self.destination_page_table_length
            if self.destination_page_table_index == length:
                return
            else:
                self.recurs_till_end()

    def extract_url_from_row(self):
        soup = bs4.BeautifulSoup(self.destination_page_content.text, features="html.parser")
        if self.destination_page_table_length == None:
            self.destination_page_table_length = len(soup.select("tbody tr .field-__str__ a"))
        url = soup.select("tbody tr .field-__str__ a")[self.destination_page_table_index].get("href")
        check_css = "tbody tr .field-processing img"
        check = is_processing_row(bs4, self.destination_page_content.text, check_css, self.destination_page_table_index)
        if check:
            self.destination_page_current_table_index_url = "http://134.209.15.93:8000" + url
        else:
            self.destination_page_current_table_index_url = ""
        if self.destination_page_table_index != self.destination_page_table_length:
            self.destination_page_table_index += 1

    def process_index_url(self):
        with self._session as session:
            req = session.get(self.destination_page_current_table_index_url)
            self.recurs_process_index_url(req.text, 0)

    def recurs_process_index_url(self, page_content, count):
        soup = bs4.BeautifulSoup(page_content, features="html.parser")
        visible_field_length = len(soup.select("tbody tr .field-subreddit input")) - 2
        count = count
        subreddit = soup.select("tbody tr .field-subreddit input")[count].get("value")
        reddit_user_name = soup.select("tbody tr .field-accounts p")[count].getText()
        error_field = soup.select("tbody tr .field-error p")[count].getText()
        css_selector = "tbody tr .field-processed p img"
        processing_row = is_processing_row(bs4, page_content, css_selector, count)
        if processing_row:
            if not error_field:
                self.active_subreddit_name = subreddit
                self.active_destination_page_url = soup
                unique_search = f"subreddit:{subreddit} author:{reddit_user_name}"
                self.search_reddit(unique_search)
        if count == visible_field_length:
            return
        else:
            count += 1
            self.recurs_process_index_url(page_content, count)

    def search_reddit(self, search_params):
        for submission in self.sub.search(search_params, sort="new"):
            now = int(time.time())
            time_difference = now - int(submission.created_utc)
            if int(time_difference) <= 3600:
                post_url = f"https://www.reddit.com{submission.permalink}"
                self.post_to_sheet(post_url)

    def post_to_sheet(self, post_url):
        sheet = self.client.open("Reddit operating sheet request").get_worksheet(0)
        if self.not_already_in_sheet(post_url):
            row = ["", "", "", "", "", "", post_url]
            sheet.append_row(row)
            self.post_new_order(self.active_destination_page_url, post_url)

    def not_already_in_sheet(self, post_url):
        sheet = self.client.open("Reddit operating sheet request").get_worksheet(0)
        cell_list = sheet.findall(post_url)
        return len(cell_list) == 0

    def post_new_order(self, page_soup, post_url):
        title = page_soup.select("input[name=title1]")[0].get("value")
        customer = f"{title}, {self.active_subreddit_name}"
        url = post_url
        start_delay = page_soup.select("input[name='action_timeout']")[0].get("value")
        qty = page_soup.select("#id_upvotes_qty")[0].get("value")
        action_timeout = page_soup.select("input[name='upvotes_action_timeout']")[0].get("value")
        with self._session as session:
            req = session.get(self.new_order)
            token = self.extract_csrftoken(req)

            payload = {
                "csrfmiddlewaretoken" : f"{token}",
                "customer" : customer,
                "url"	: url,
                "start_delay" : start_delay,
                "qty" : qty,
                "action_timeout" : action_timeout,
                "active" : "on",
                "_save" : "Save"
            }
             
            session.post(self.new_order, data=payload)


if __name__ == "__main__":
    rdp = RedditDjangoPublication()
    rdp.init_session()
    rdp.working_session()
    rdp.recurs_till_end()