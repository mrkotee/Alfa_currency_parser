from robobrowser import RoboBrowser
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
    parser = Currency_parser()
    cur_rates = parser.parse_currency_alfabank()

    new_rates = check_and_save_rates_to_base(cur_rates)

    return new_rates


if __name__ == "__main__":
    # new_rates = parse_and_save_rates()
    #
    # print(new_rates)


    parser = Currency_parser()
    cur_rates = parser.parse_currency_alfabank()
    print("alfa rates", cur_rates)
    cur_rates = parser.parse_currency_bankiru()
    print("banki rates", cur_rates)

    check_and_save_rates_to_base(cur_rates)


