#!/usr/bin/env python

import urllib2, re, datetime, time

from bs4 import BeautifulSoup

"""
    PURPOSE
    =======
    Scrapes the Seattle Lobbyist Disclosure web site (http://www2.seattle.gov/ethics/lobbyists/lobbyhome.asp) 
    and puts the lobbyist disclosure data into a database.

    GENERAL INFORMATION
    ===================
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

    REPORT TYPES
    ============
    There are four report types:
    * Basic Lobbyist Registration Statement ("Basic Registration")
    * Lobbyist Registration Statement ("Client/Employer Registration")
    * Report of Expenditures ("Quarterly Expense Report")
    * Report of Expenditures ("Employer's Annual Expense Report")

    TODO: The last two report types show up with the same text in the header but are structured differently.
            Will probably need to scrape the distinct type from the listing pages since once you hit the report you can't 
            tell what you're dealing with other than the differing structure.

    The report types are identified in the header box at the top of the report, specifically the text between "SEEC - " and 
    the filing date. The filing date line is preceded by a <br /> and the filing date line begins with "Filed". The text in 
    parentheses and quotation marks above -- e.g. ("Client/Employer Registration") -- indicates the value of the "Type" 
    column on the report listing pages.

    REPORT AMENDMENTS
    =================
    From what I can discern original filings are never updated. If an amendment is filed the amendment gets a new filing date
    and the report will have a "Report History" section at the top of the report. The Report History section also contains links 
    to the original report and any previous amendments (though I have yet to see one that contains more than one past amendment).
    If this analysis is correct, this means that once a report has been scraped we don't have to go back to check for updates 
    to past reports.

    ADDITIONAL ASSUMPTIONS
    ======================
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

    # get each report, parse out data points, and save to db
    for guid in report_guids:
        # get the reports
        report = {}

        report['guid'] = guid.replace('{', '').replace('}', '')
        report['permalink'] = individual_report_base_url + report['guid']

        report_soup = BeautifulSoup(urllib2.urlopen(report['permalink']))

        # Report Type
        # Text in the 'Title' class td prior to the filed date line
        report['report_type'] = report_soup.find('td', class_='Title').text.split('\r')[0][7:].upper()

        # Filed Date (common across all report types)
        # Text in the 'Title' class td after the 'SEEC - REPORT TYPE<br/>' text
        # Date is in the format 'Filed Aug 14 2012  5:25PM' (N.B. the two spaces after the date before the time, 
        # and the lack of space between the time and PM)
        # We'll go through a few steps to clean this up so we have less risk of it breaking.
        filed_date = report_soup.find(class_='Title').text
        filed_date = re.search('Filed[\w\s\:]{0,}', filed_date).group(0)
        filed_date = filter(None, filed_date.split(' ')[1:])
        filed_date = ' '.join(filed_date)

        dt_filed = time.strptime(filed_date, '%b %d %Y %I:%M%p')
        report['dt_filed'] = datetime.datetime.fromtimestamp(time.mktime(dt_filed)).isoformat()

        # Amendment Data
        # If a report has amendments there will be a td with 'Originally filed:' in a Report History section at the top
        # TODO: Not sure if amendments only apply to quarterly expense reports. Do this for all types for now.
        report['dt_originally_filed'] = None
        report['original_report_link'] = None
        report['dt_amendment_filed'] = None
        report['amendment_report_link'] = None

        if report_soup.find('td', text=re.compile('Report History')):
            # date/time values in the report history section are in format 4/14/2009 10:35:06 AM
            # date originally filed
            dt_originally_filed_node = report_soup.find('td', text=re.compile('Originally filed:'))
            dt_originally_filed = dt_originally_filed_node.next_sibling.next_sibling.text
            dt_originally_filed = time.strptime(dt_originally_filed, '%m/%d/%Y %I:%M:%S %p')
            report['dt_originally_filed'] = datetime.datetime.fromtimestamp(time.mktime(dt_originally_filed)).isoformat()

            # original report guid/link
            for node in dt_originally_filed_node.next_siblings:
                guid_match = re.search(guid_regex, str(node))
                if guid_match:
                    report['original_report_link'] = individual_report_base_url + guid_match.group(0)

            # date amendment filed
            dt_amendment_filed_node = report_soup.find('td', text=re.compile('Amendment filed:'))
            dt_amendment_filed = dt_amendment_filed_node.next_sibling.next_sibling.text
            dt_amendment_filed = time.strptime(dt_amendment_filed, '%m/%d/%Y %I:%M:%S %p')
            report['dt_amendment_filed'] = datetime.datetime.fromtimestamp(time.mktime(dt_amendment_filed)).isoformat()

            # get amendment report link
            for node in dt_amendment_filed_node.next_siblings:
                guid_match = re.search(guid_regex, str(node))
                if guid_match:
                    report['amendment_report_link'] = individual_report_base_url + guid_match.group(0)

            # date this amendment filed -- redundant with the filed date only with seconds in the time
            # dt_this_amendment_filed = report_soup.find('td', text=re.compile('This amendment filed:')).next_sibling.next_sibling.text
            # dt_this_amendment_filed = time.strptime(dt_this_amendment_filed, '%m/%d/%Y %I:%M:%S %p')
            # dt_this_amendment_filed = datetime.datetime.fromtimestamp(time.mktime(dt_this_amendment_filed)).isoformat()

        # data extraction diverges based on report type from here out
        if report['report_type'] == 'BASIC LOBBYIST REGISTRATION STATEMENT':
            # Lobbyist/Filer Info
            # TODO: need to match the name with a filer ID -- for this reason does it make more sense to grab things by lobbyist instead of date?
            filer = {}

            # Because basic registrations may have multiple tables with the same labels in the left column (e.g. 'Street Address 1')
            # need to work at the 'table' level based on the text in the header row of the table
            filer_table = report_soup.find('td', text=re.compile('Filer')).parent.parent

            filer['name'] = filer_table.find('td', text=re.compile('Name')).next_sibling.text.strip()

            # Some basic registrations will have an organization row after the name, some won't
            organization_node = filer_table.find('td', text=re.compile('Organization'))
            if organization_node:
                filer['organization'] = organization_node.next_sibling.text.strip()
            else:
                filer['organization'] = None

            filer['address1'] = filer_table.find('td', text=re.compile('Street Address 1')).next_sibling.text.strip()
            filer['address2'] = filer_table.find('td', text=re.compile('Street Address 2')).next_sibling.text.strip()
            filer['city'] = filer_table.find('td', text=re.compile('City')).next_sibling.text.strip()
            filer['state'] = filer_table.find('td', text=re.compile('State')).next_sibling.text.strip()
            filer['zip'] = filer_table.find('td', text=re.compile('Zip')).next_sibling.text.strip()
            filer['phone'] = filer_table.find('td', text=re.compile('Phone')).next_sibling.text.strip()
            filer['email'] = filer_table.find('td', text=re.compile('EMail')).next_sibling.text.strip()

            report['filer'] = filer

            # temporary Seattle address info (optional)
            temp_address_table = report_soup.find('td', text=re.compile('Temporary Seattle Address (if applicable)')).parent.parent

            print report
            raise


if __name__ == '__main__':
	main()
