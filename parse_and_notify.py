import os, time
from datetime import datetime as dt
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from settings import admin_user_id, base_path, userbase_path
from alc_base import CurrencyTypes, CurrencyRates, PurchasedCurrency, Users
from alfa_parser import parse_and_save_rates

    

LOG_FILENAME = 'alfaparser.log'
# logging.getLogger("requests.packages.urllib3")
# logging.propagate = True
logging.basicConfig(filename=LOG_FILENAME, level=logging.DEBUG,
                    format=u'%(levelname)-8s [%(asctime)s]  %(message)s')
logTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


logging.info("parse rates")
new_rates = parse_and_save_rates()

# alfa_cur_engine = create_engine('sqlite:///%s' % base_path, echo=False)
# alfa_cur_Session = sessionmaker(bind=alfa_cur_engine)
# alfa_cur_session = alfa_cur_Session()
#
# ### for test ####
# new_rates = alfa_cur_session.query(CurrencyRates).all()[:2]
# print(*[rate.date for rate in new_rates])
# # print(new_rates[0].date.date() == dt.now().date())

if new_rates:
    logging.info("new rates")
    from currency_bot import bot

    alfa_u_engine = create_engine('sqlite:///%s' % userbase_path, echo=False)
    alfa_u_Session = sessionmaker(bind=alfa_u_engine)
    alfa_u_session = alfa_u_Session()

    alfa_cur_engine = create_engine('sqlite:///%s' % base_path, echo=False)
    alfa_cur_Session = sessionmaker(bind=alfa_cur_engine)
    alfa_cur_session = alfa_cur_Session()

    new_rates = [alfa_cur_session.query(CurrencyRates).get(rate_id) for rate_id in new_rates]

    cur_types = alfa_cur_session.query(CurrencyTypes).all()
    msg_text = "New rates:\nCurrency  buy  sell\n"
    # msg_text += "\n".join(["{currency}  {buy}({ineq_buy})  {sell}({ineq_sell})".format(
    #         currency=alfa_cur_session.query(CurrencyTypes).get(rate.currency_type).abbreviation,
    #         buy=rate.to_buy,
    #         ineq_buy=,
    #         ineq_sell=,
    #         sell=rate.to_sell,
    #     ).rjust(19) for rate in new_rates])
    for rate in new_rates:

        last_cur_rate = alfa_cur_session.query(CurrencyRates).filter(
            CurrencyRates.currency_type == rate.currency_type).order_by(
            CurrencyRates.id).all()[-2]
        cur_type = alfa_cur_session.query(CurrencyTypes).filter(CurrencyTypes.id == rate.currency_type).first()
        msg_text += "{currency}  {buy}({ineq_buy}) {sell}({ineq_sell})\n".format(
            currency=cur_type.abbreviation,
            buy=rate.to_buy,
            ineq_buy=round(rate.to_buy - last_cur_rate.to_buy, 3),
            sell=rate.to_sell,
            ineq_sell=round(rate.to_sell - last_cur_rate.to_sell, 3),
        )

    users = alfa_u_session.query(Users).filter(Users.active == True).all()
    messages = {}
    for user in users:
        can_be_selled = []
        user_sums = []
        for rate in new_rates:
            user_purchased = alfa_cur_session.query(PurchasedCurrency).filter(
                PurchasedCurrency.user_id == user.id).filter(
                PurchasedCurrency.currency_type == rate.currency_type).filter(
                PurchasedCurrency.selled == False).all()

            user_summ = 0.0
            for purchase in user_purchased:
                # print(purchase.waiting_for, rate.to_buy)
                # if rate.to_buy >= purchase.waiting_for:
                #     can_be_selled.append(purchase)
                user_summ += float(purchase.currency_value)
            user_sums.append(
                "{currency} {value} == {rubles}".format(
                currency=rate.currency_type,
                value=round(user_summ, 2),
                rubles=round(user_summ*rate.to_buy))
            )

        # if can_be_selled:
        #     user_msg_text = msg_text + "\n\nYou can sell:\n"
        #     user_msg_text += "\n".join(["{currency} {value} purchased on {date}".format(
        #         currency=next((c_type.abbreviation for c_type in cur_types if c_type.id == purchase.currency_type)),
        #         value=purchase.currency_value,
        #         date=purchase.date.date(),
        #     ) for purchase in can_be_selled])
        if user_sums:
            user_msg_text = msg_text + "\n\nYou have:\n"
            user_msg_text += "\n".join([sums_text for sums_text in user_sums])

        else:
            user_msg_text = msg_text

        messages[user.chat_id] = user_msg_text

    alfa_cur_session.close()

    for user_id, msg_text in messages.items():
        logging.debug("send msg to {user_id}")
        bot.send_message(user_id, msg_text)

