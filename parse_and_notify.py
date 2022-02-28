# python 3.5
import time
import logging
from settings import admin_user_id, base_path, userbase_path
from alchemy_base.alc_models import CurrencyTypes, CurrencyRates, PurchasedCurrency, Users
from alchemy_base.connector import create_session
from alfa_parser import parse_and_save_rates


LOG_FILENAME = 'alfaparser.log'
# logging.getLogger("requests.packages.urllib3")
# logging.propagate = True
logging.basicConfig(filename=LOG_FILENAME, level=logging.INFO,
                    format=u'%(levelname)-8s [%(asctime)s]  %(message)s')
logTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def write_main_part_of_msg(new_rates, currency_session, cur_types):
    msg_text = "New rates:\nCurrency  buy  sell\n"
    for rate in new_rates:
        last_currency_rate = currency_session.query(CurrencyRates).filter(
            CurrencyRates.currency_type == rate.currency_type).order_by(
            CurrencyRates.id).all()[-2]
        msg_text += "{currency}  {buy}({ineq_buy}) {sell}({ineq_sell})\n".format(
            currency=next((c_type.abbreviation for c_type in cur_types if c_type.id == rate.currency_type)),
            buy=rate.to_buy,
            ineq_buy=round(rate.to_buy - last_currency_rate.to_buy, 3),
            sell=rate.to_sell,
            ineq_sell=round(rate.to_sell - last_currency_rate.to_sell, 3),
        )

    return msg_text


def add_user_part_to_msg(main_part_msg, user_sums, can_be_selled, cur_types):
    if not user_sums:
        return main_part_msg

    user_msg_text = main_part_msg + "\n"

    user_msg_text += "\nYou have:\n"
    user_msg_text += "\n".join([sums_text for sums_text in user_sums])
    if can_be_selled:
        user_msg_text += "\nYou can sell:\n"
        user_msg_text += "\n".join(["{currency} {value} purchased on {date}".format(
            currency=next((c_type.abbreviation for c_type in cur_types if c_type.id == purchase.currency_type)),
            value=purchase.currency_value,
            date=purchase.date.date(),
        ) for purchase in can_be_selled])

    return user_msg_text


def get_user_purchases_in_str(user_id, new_rates, currency_session, cur_types):
    can_be_selled = []
    user_sums = []
    for rate in new_rates:
        user_purchased = currency_session.query(PurchasedCurrency).filter(
            PurchasedCurrency.user_id == user_id).filter(
            PurchasedCurrency.currency_type == rate.currency_type).filter(
            PurchasedCurrency.selled == False).all()

        user_summ = 0.0
        for purchase in user_purchased:
            if rate.to_buy >= purchase.waiting_for:
                can_be_selled.append(purchase)
            user_summ += float(purchase.currency_value)
        user_sums.append(
            "{currency} {value} == {rubles}".format(
                currency=next((c_type.abbreviation for c_type in cur_types if c_type.id == rate.currency_type)),
                value=round(user_summ, 2),
                rubles=round(user_summ*rate.to_buy))
        )
    return user_sums, can_be_selled


def main():
    logging.info("parse rates")
    new_rates_ids = parse_and_save_rates()

    if not new_rates_ids:
        return None

    logging.info("new rates")
    from currency_bot import bot

    alfa_u_session = create_session(userbase_path)
    alfa_cur_session = create_session(base_path)

    new_rates = [alfa_cur_session.query(CurrencyRates).get(rate_id) for rate_id in new_rates_ids]

    cur_types = alfa_cur_session.query(CurrencyTypes).all()

    msg_text = write_main_part_of_msg(new_rates, alfa_cur_session, cur_types)

    users = alfa_u_session.query(Users).filter(Users.active == True).all()
    messages = {}
    for user in users:
        user_sums, can_be_selled = get_user_purchases_in_str(user.id, new_rates, alfa_cur_session, cur_types)

        messages[user.chat_id] = add_user_part_to_msg(msg_text, user_sums, can_be_selled, cur_types)

    alfa_u_session.close()
    alfa_cur_session.close()

    for user_id, msg_text in messages.items():
        logging.debug("send msg to {user_id}")
        bot.send_message(user_id, msg_text)


main()
