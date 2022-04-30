# python 3.5
import random

import requests
from requests.exceptions import ConnectionError
from urllib3.exceptions import ProtocolError
import time
from datetime import datetime as dt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from alchemy_base.alc_models import CurrencyTypes, CurrencyRates
from settings import base_path


def parse_currency_alfa_json():
    """parse alfa api
    :return currencies dict"""

    def parse_with_pure_request():
        date_now = dt.now()
        url = "https://alfabank.ru/api/v1/scrooge/currencies/alfa-rates?\
        currencyCode.in=USD,EUR,CHF,GBP&rateType.eq=makeCash&lastActualForDate.\
        eq=true&clientType.eq=standardCC&date.lte={year}-{mounth}-{day}T{hour}:{minute}:18+03:00".format(
            year=date_now.year,
            mounth=date_now.strftime('%m'),
            day=date_now.strftime('%d'),
            hour=date_now.strftime('%H'),
            minute=date_now.strftime('%M'),
            )
        url = "https://alfabank.ru/api/v1/scrooge/currencies/alfa-rates"
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.74 Safari/537.36"}
        response = requests.get(url, headers=headers)


        return response

    def parse_with_session():
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.74 Safari/537.36"}

        session = requests.session()
        session.headers = headers
        response = session.get("https://alfabank.ru")
        time.sleep(random.randint(3, 10))
        response = session.get("https://alfabank.ru/currency/")
        # "https://alfabank.ru/api/v1/scrooge/currencies/alfa-rates"
        rates = ",".join(["USD","EUR","CHF","GBP"])
        date = dt.now().replace(microsecond=0).isoformat() + "+03:00"
        url = "https://alfabank.ru/api/v1/scrooge/currencies/alfa-rates?currencyCode.in={codes}&rateType.eq=makeCash&" \
              "lastActualForDate.eq=true&clientType.eq=standardCC&date.lte={date}".format(codes=rates, date=date)
        response = session.get(url)
        return response

    response = parse_with_session()

    res = {}
    for c in response.json()["data"]:
        if c['currencyCode'].lower() == "usd" or c['currencyCode'].lower() == "eur":
            res[c['currencyCode'].upper()] = {}
            act_rate = c['rateByClientType'][0]['ratesByType'][0]['lastActualRate']
            s_date = dt.strptime(act_rate['date'][:act_rate['date'].find("+")], "%Y-%m-%dT%H:%M:%S")  # del timezone

            res[c['currencyCode'].upper()]['buy'] = act_rate['buy']['originalValue']
            res[c['currencyCode'].upper()]['sell'] = act_rate['sell']['originalValue']
            res[c['currencyCode'].upper()]['date'] = s_date
    return res


def check_and_save_rates_to_base(rates_dict):
    """
        :return list of new rates ids in base if add this to base
        :return empty list if checked rates already in base
    """

    engine = create_engine('sqlite:///%s' % base_path, echo=False)
    session = sessionmaker(bind=engine)()

    new_rates_id = []
    cur_types = {c_type.abbreviation: c_type for c_type in session.query(CurrencyTypes).all()}
    for cur_type, cur_rate in rates_dict.items():
        # add new type of currency to base
        if not cur_types.get(cur_type):
            new_type = CurrencyTypes(abbreviation=cur_type)
            session.add(new_type)
            session.commit()
            cur_types[cur_type] = new_type

        cur_base_id = cur_types[cur_type].id

        # check what rates not equal last rates in base
        rates_in_base = session.query(CurrencyRates).filter(
            CurrencyRates.currency_type == cur_base_id).order_by(
            CurrencyRates.id).all()
        if rates_in_base:
            last_cur_rate = rates_in_base[-1]
            if last_cur_rate.to_buy == cur_rate['buy']:  # we interested only in bank buy rates
                continue

        new_rate = CurrencyRates(cur_base_id, cur_rate['buy'], cur_rate['sell'])
        session.add(new_rate)
        session.commit()
        new_rates_id.append(new_rate.id)

    session.close()
    return new_rates_id


def parse_and_save_rates():
    for _ in range(5):
        try:
            currency_rates = parse_currency_alfa_json()
            break
        except (ConnectionError, KeyError):
            time.sleep(13)

    new_rates = check_and_save_rates_to_base(currency_rates)

    return new_rates


if __name__ == "__main__":
    for _ in range(5):
        try:
            currency_rates = parse_currency_alfa_json()
            break
        except (ConnectionError, KeyError) as e:  # , ConnectionResetError, ProtocolError
            print("expt", e)
            time.sleep(13)
    print('alfa rates', currency_rates)
    check_and_save_rates_to_base(currency_rates)
    print("rates saved in base")
