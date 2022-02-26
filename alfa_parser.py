# python 3.5
import requests
from datetime import datetime as dt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from alchemy_base.alc_models import CurrencyTypes, CurrencyRates
from settings import base_path


def parse_currency_alfa_json():
    """parse alfa api
    :return currencies dict"""
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

    response = requests.get(url)

    res = {}
    for c in response.json()["data"]:
        if c['currencyCode'].lower() == "usd" or c['currencyCode'].lower() == "eur":
            res[c['currencyCode'].upper()] = {}
            act_rate = c['rateByClientType'][0]['ratesByType'][0]['lastActualRate']
            s_date = dt.strptime(act_rate['date'][:-6], "%Y-%m-%dT%H:%M:%S")  # del timezone

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
    currency_rates = parse_currency_alfa_json()
    new_rates = check_and_save_rates_to_base(currency_rates)

    return new_rates


if __name__ == "__main__":
    try:
        cur_rates = parse_currency_alfa_json()
        print('alfa rates', cur_rates)
    except Exception as e:
        print("alfa parser isn't work")
        print(e)
    check_and_save_rates_to_base(cur_rates)
    print("rates saved in base")
