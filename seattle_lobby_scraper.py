#!/usr/bin/env python

import urllib2, re

from bs4 import BeautifulSoup

"""
    Scrapes the Seattle Lobbyist Disclosure web site (http://www2.seattle.gov/ethics/lobbyists/lobbyhome.asp) 
    and puts the lobbyist disclosure data into a database.

    From what I can discern filings are never updated, but rather if a prior report is incorrect an amendment 
    must be filed, and the amendment gets a new filing date. If this is correct, this means that once a report 
    has been scraped we don't have to go back to check for updates to past reports.

    As of 2/24/2013 the following information is valid:
    * main ethics site URL: http://www2.seattle.gov/ethics
    * lobbying home URL: http://www2.seattle.gov/ethics/lobbyists/lobbyhome.asp
    * lobbying reports home URL: http://www2.seattle.gov/ethics/lobbyists/reports.asp
    * lobbyist-specific page URL: http://www2.seattle.gov/ethics/lobbyists/reports.asp?intLobbyistID=LOBBYIST_ID
      (lobbyist ID is an integer)
    * monthly report URL: http://www2.seattle.gov/ethics/lobbyists/reports.asp?intYear=YEAR&intMonth=MONTH
      (year is four-digit year; month is integer with no leading zero for months < 10)
    * individual report URLs (in popup windows): http://www2.seattle.gov/ethics/eldata/filings/popfiling.asp?prguid={REPORT_GUID}
      (report GUID is a standard 36-character guid; note that the URL *does contain* the curly braces shown above)
    * the lobbying reports home URL has lobbyist-specific and year/month-specific links in tabs but these tabs are loaded 
      when the page loads so they're all in the HTML source
    * individual reports are viewable only via a button labeled "PopUp" on date-based and lobbyist-based report pages
    * individual reports do have a permalink URL listed at the bottom of the report popup labeled "Fixed link to this report:", 
      and this URL is the same URL as in the popup link but without the curly braces, e.g. 
      http://www2.seattle.gov/ethics/eldata/filings/popfiling.asp?prguid=REPORT_GUID (N.B. the lack of curly braces)

    Additional Assumptions:
    * Looking at both the lobbyist-specific report listings and the date-range report listings is redundant, so we'll use the 
      date range as the main means of getting reports since we get more bang for our buck (i.e. more report guids per http call)
      that way.
    * We'll use the lobbyist-specific links to add new lobbyists and verify and update the existing lobbyist information in the database.
"""

def main():
    # URLs and other handy variables
    base_url = 'http://www2.seattle.gov/ethics'
    lobbyists_base_url = base_url + '/lobbyists'
    individual_report_base_url = base_url + '/eldata/filings/popfiling.asp?prguid='

    guid_regex = re.compile(r'\{[a-zA-Z0-9]{8}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{12}\}')

    # get links on the lobbying home page and parse out into lobbyist pages vs. date range pages
    lobbying_home_html = BeautifulSoup(urllib2.urlopen(lobbyists_base_url + '/reports.asp').read())

    lobbyist_links = []
    date_range_links = []

    for link in lobbying_home_html.find_all('a'):
        if 'reports.asp?intLobbyistID=' in link.get('href'):
            lobbyist_links.append(lobbyists_base_url + '/' + link.get('href'))
        elif 'reports.asp?intYear=' in link.get('href'):
            date_range_links.append(lobbyists_base_url + '/' + link.get('href'))

    #print lobbyist_links
    #print date_range_links

    # TODO: add new/update existing lobbyists as needed

    # loop over and get the unique report guids from the date-range links
    report_guids = []

    for link in date_range_links:
        soup = BeautifulSoup(urllib2.urlopen(link).read())
        soup = str(soup)

        guids = re.findall(guid_regex, soup)
        # there are duplicates in the html source so convert to a set
        guids = set(guids)

        for guid in guids:
            report_guids.append(guid)

    # in case we got any duplicate guids across pages, convert final list to a set
    report_guids = set(report_guids)

    print len(report_guids)

    # TODO: get each report, parse out data points, and save to db


if __name__ == '__main__':
	main()
