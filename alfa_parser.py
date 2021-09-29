# python 3.5
from robobrowser import RoboBrowser
import requests
from datetime import datetime as dt
from settings import base_path


class Currency_parser:
    USERAGENT = "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36"


    def __init__(self):
        self.browser = RoboBrowser(history=True, cache=True, parser='lxml', user_agent=self.USERAGENT)

    def parse_currency_bankiru(self):
        main_url = "http://www.banki.ru/products/currency/bank/alfabank/moskva/"

        self.browser.open(main_url)

        tables = self.browser.find_all(name='table', attrs={'class': "standard-table"})

        CurrencyRates = {}
        rows = tables[0].find_all('tr')
        for row in rows:
            cols = [td.text.strip() for td in row.find_all('td')]

            if cols:
                CurrencyRates[cols[0]] = {"buy": float(cols[3].replace(',', '.')),
                                          "sell": float(cols[4].replace(',', '.')),
                                          }

        return CurrencyRates

    def parse_currency_alfabank(self):
        main_url = "https://alfabank.ru/_/rss/_currency.html"

        self.browser.open(main_url)

        # print(self.browser.select)

        currencies = self.browser.find_all("tr")

        dollar, euro = list(currencies[1]), list(currencies[2])

        return {"EUR": {"buy": float(euro[1].text.replace(',', '.')), "sell": float(euro[2].text.replace(',', '.')), },
                "USD": {"buy": float(dollar[1].text.replace(',', '.')), "sell": float(dollar[2].text.replace(',', '.')), },
                }


def parse_currency_alfa_json():
    def parse_old_json():
        url = "https://alfabank.ru/ext-json/0.2/exchange/cash?offset=0&limit=2&mode=rest"

        r = requests.get(url)
        res = {}
        for c, v in r.json().items():
            if c.lower() == "usd" or c.lower() == "eur":
                res[c.upper()] = {}
                last_res = ()
                for s in v:
                    s_type = s['type']
                    s_date = dt.strptime(s['date'], "%Y-%m-%d %H:%M:%S")
                    s_value = s['value']
                    if last_res:
                        if last_res[3] > s_date and last_res[:2] == (c, s_type):
                            last_res = (c, s_type, s_value, s_date)
                        else:
                            res[c.upper()][s_type] = s_value
                            res[c.upper()]['date'] = s_date
                            last_res = (c, s_type, s_value, s_date)

                    else:
                        last_res = (c, s_type, s_value, s_date)
                        res[c.upper()][s_type] = s_value
                        res[c.upper()]['date'] = s_date
        return res
                    
    def parse_api_json():
        ## https://alfabank.ru/api/v1/scrooge/currencies/alfa-rates?currencyCode.in=USD,EUR,CHF,GBP&rateType.eq=makeCash&lastActualForDate.eq=true&clientType.eq=standardCC&date.lte=2021-09-28T10:25:18+03:00
        url = "https://alfabank.ru/api/v1/scrooge/currencies/alfa-rates?\
currencyCode.in=USD,EUR,CHF,GBP&rateType.eq=makeCash&lastActualForDate.\
eq=true&clientType.eq=standardCC&date.lte={year}-{mounth}-{day}T{hour}:{minute}:18+03:00".format(
            year=dt.now().year,
            mounth=dt.now().strftime('%m'),
            day=dt.now().strftime('%d'),
            hour=dt.now().strftime('%H'),
            minute=dt.now().strftime('%M'),
            )

        r = requests.get(url)
        # print(r.json()["data"])  # [{'currencyCode': 'CHF', 'rateByClientType': [{'clientType': 'standardCC', 'ratesByType': [{'rateType': 'makeCash', 'ratesForPeriod': [], 'lastActualRate': {'sell': {'originalValue': 79.31}, 'buy': {'originalValue': 77.81}, 'date': '2021-09-28T18:09:00+03:00'}}]}]}, {'currencyCode': 'EUR', 'rateByClientType': [{'clientType': 'standardCC', 'ratesByType': [{'rateType': 'makeCash', 'ratesForPeriod': [], 'lastActualRate': {'sell': {'originalValue': 85.93}, 'buy': {'originalValue': 84.33}, 'date': '2021-09-28T18:09:00+03:00'}}]}]}, {'currencyCode': 'GBP', 'rateByClientType': [{'clientType': 'standardCC', 'ratesByType': [{'rateType': 'makeCash', 'ratesForPeriod': [], 'lastActualRate': {'sell': {'originalValue': 99.53}, 'buy': {'originalValue': 97.83}, 'date': '2021-09-28T18:09:00+03:00'}}]}]}, {'currencyCode': 'USD', 'rateByClientType': [{'clientType': 'standardCC', 'ratesByType': [{'rateType': 'makeCash', 'ratesForPeriod': [], 'lastActualRate': {'sell': {'originalValue': 73.68}, 'buy': {'originalValue': 72.18}, 'date': '2021-09-28T18:09:00+03:00'}}]}]}]

        res = {}
        for c in r.json()["data"]:
            if c['currencyCode'].lower() == "usd" or c['currencyCode'].lower() == "eur":
                res[c['currencyCode'].upper()] = {}
                act_rate = c['rateByClientType'][0]['ratesByType'][0]['lastActualRate']
                # s_date = act_rate['date']
                s_date = dt.strptime(act_rate['date'][:-6], "%Y-%m-%dT%H:%M:%S") # del timezone
                # s_date = dt.fromisoformat(act_rate['date'])

                res[c['currencyCode'].upper()]['buy'] = act_rate['buy']['originalValue']
                res[c['currencyCode'].upper()]['sell'] = act_rate['sell']['originalValue']
                res[c['currencyCode'].upper()]['date'] = s_date


        return res


    res_one = parse_old_json()
    res_two = parse_api_json()

    if res_two['USD']['date'] > res_one['USD']['date']:
        return res_two
    else:
        return res_one

    # return {"EUR": {"buy": float(euro[1].text.replace(',', '.')), "sell": float(euro[2].text.replace(',', '.')), },
    #         "USD": {"buy": float(dollar[1].text.replace(',', '.')),
    #                 "sell": float(dollar[2].text.replace(',', '.')), },
    #         }


def check_and_save_rates_to_base(rates_dict):
    """
        :return rate list if add this to base
        :return empty list if checked rates already in base
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from alc_base import CurrencyTypes, CurrencyRates

    engine = create_engine('sqlite:///%s' % base_path, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    new_rates = []
    cur_types = session.query(CurrencyTypes).all()
    for cur_type, cur_rate in rates_dict.items():
        if cur_type not in [c_type.abbreviation for c_type in cur_types]:
            new_type = CurrencyTypes(abbreviation=cur_type)
            session.add(new_type)
            session.commit()
            cur_types.append(new_type)

        for c_type in cur_types:
            if c_type.abbreviation == cur_type:
                cur_base_id = c_type.id

        last_cur_rate = session.query(CurrencyRates).filter(CurrencyRates.currency_type == cur_base_id).order_by(
            CurrencyRates.id).all()[-1]
        if last_cur_rate:
            if last_cur_rate.to_buy == cur_rate['buy'] or last_cur_rate.to_sell == cur_rate['sell']:
                continue

        new_rate = CurrencyRates(cur_base_id, cur_rate['buy'], cur_rate['sell'])
        session.add(new_rate)
        session.commit()
        new_rates.append(new_rate.id)

    return new_rates


def parse_and_save_rates():
    try:
        parser = Currency_parser()
        cur_rates = parser.parse_currency_alfabank()
    except:
        cur_rates = parse_currency_alfa_json()
    new_rates = check_and_save_rates_to_base(cur_rates)

    return new_rates


if __name__ == "__main__":
    # new_rates = parse_and_save_rates()
    #
    # print(new_rates)


    parser = Currency_parser()
    try:
        cur_rates = parser.parse_currency_alfabank()
        print("alfa  rates", cur_rates)
    except:
        print("alfa browser isn't work")

    try:
        cur_rates = parser.parse_currency_bankiru()
        print("banki rates", cur_rates)
    except:
        print("banki browser isn't work")

    try:
        cur_rates = parse_currency_alfa_json()
        print('alfa json rates', cur_rates)
    except:
        print("alfa json isn't work")

    check_and_save_rates_to_base(cur_rates)





