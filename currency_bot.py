import telebot
from telebot import types
import sys
import os
import logging
import time
import re
from datetime import datetime as dt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import IntegrityError, InvalidRequestError
try:
    from settings import token, admin_user_id, base_path, userbase_path
    from alc_base import CurrencyTypes, CurrencyRates, PurchasedCurrency, Users
except ImportError:
    from alfa_bot.settings import token, admin_user_id, base_path, userbase_path
    from alfa_bot.alc_base import CurrencyTypes, CurrencyRates, PurchasedCurrency, Users


LOG_FILENAME = 'alfabot.log'
# logging.getLogger("requests.packages.urllib3")
# logging.propagate = True
logging.basicConfig(filename=LOG_FILENAME, level=logging.DEBUG,
                    format=u'%(levelname)-8s [%(asctime)s]  %(message)s')
logTime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


bot = telebot.TeleBot(token, threaded=False)

telebot.logger = logging

alfa_u_engine = create_engine('sqlite:///%s' % userbase_path, echo=False)
alfa_u_Session = sessionmaker(bind=alfa_u_engine)
alfa_u_session = scoped_session(alfa_u_Session)

alfa_cur_engine = create_engine('sqlite:///%s' % base_path, echo=False)
alfa_cur_Session = sessionmaker(bind=alfa_cur_engine)
alfa_cur_session = scoped_session(alfa_cur_Session)


def check_user_in_base(chat_id):
    try:
        user_in_base = alfa_u_session.query(Users).filter(Users.chat_id==chat_id).first()
    except InvalidRequestError as e:
        alfa_u_session.rollback()
        user_in_base = alfa_u_session.query(Users).filter(Users.chat_id==chat_id).first()
    return user_in_base


def check_user_in_base_dec(func):
    def decorator(*args, **kwargs):
        # print(list(_arg + '\n' for _arg in args[0].__dict__.keys()))
        # print(args[0].from_user.id)
        message = args[0]
        try:
            chat_id = message.chat.id
        except:
            chat_id = message.from_user.id
        try:
            user_in_base = alfa_u_session.query(Users).filter(Users.chat_id==chat_id).first()
        except InvalidRequestError as e:
            alfa_u_session.rollback()
            user_in_base = alfa_u_session.query(Users).filter(Users.chat_id==chat_id).first()

        if user_in_base:
            # bot.send_message(chat_id, 'you in base')
            args = [*args]
            args.append(user_in_base)
            func(*args, **kwargs)

        else:
            bot.send_message(chat_id, 'you have no power here!\nuse /start')

    return decorator


@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    username = message.chat.username

    user_in_base = check_user_in_base(chat_id)

    if not user_in_base:
        alfa_u_session.add(Users(chat_id, username))
        alfa_u_session.commit()
        msg = "Здравствуй, *{}*!\nУведомление о курсах валют АльфаБанка включено!".format(username)

    elif not user_in_base.active:
        user_in_base.active = True
        msg = "С возвращением, *{}*!\nУведомление о курсах валют АльфаБанка включено!".format(username)

    else:
        msg = """Уведомления уже включены!\nДоступные команды:
        /stop - прекратить уведомления
        /add_purchased - добавить покупку
        /purchased_list - список покупок
        /rate - действующие курсы
                """

    bot.send_message(chat_id, msg) # parse_mode='Markdown'


@bot.message_handler(commands=['stop'])
def send_goodbye(message):
    chat_id = message.chat.id
    username = message.chat.username

    user_in_base = check_user_in_base(chat_id)

    if not user_in_base:
        user = Users(chat_id, username)
        user.active = False
        alfa_u_session.add(user)
        alfa_u_session.commit()

    else:
        user_in_base.active = False
        alfa_u_session.commit()

    msg = "Уведомления отключены!"

    bot.send_message(chat_id, msg, parse_mode='Markdown')


@bot.message_handler(commands=['rate'])
def send_last_rate(message):
    chat_id = message.chat.id

    cur_types = alfa_cur_session.query(CurrencyTypes).all()
    new_rates = []
    for cur_type in cur_types:
        last_cur_rate = \
        alfa_cur_session.query(CurrencyRates).filter(CurrencyRates.currency_type == cur_type.id).order_by(
            CurrencyRates.id)[-1]
        new_rates.append(last_cur_rate)

    msg_text = "Last rates:\n"
    msg_text += "Time".center(16)
    msg_text += " Currency  buy  sell\n"
    msg_text += "\n".join(["{date} {currency}  {buy}  {sell}".format(
        date=rate.date.strftime("%Y/%m/%d %H:%M"),
        currency=next(c_type.abbreviation for c_type in cur_types if c_type.id == rate.currency_type),
        buy=rate.to_buy,
        sell=rate.to_sell,
    ).rjust(19) for rate in new_rates])

    bot.send_message(chat_id, msg_text)


@bot.message_handler(commands=['add_purchased'])
@check_user_in_base_dec
def add_purchased(message, user_in_base):
    chat_id = message.chat.id

    users_purchases = alfa_cur_session.query(PurchasedCurrency).filter(PurchasedCurrency.user_id == user_in_base.id).all()

    new_purchase = PurchasedCurrency(currency_type_id=1, user_id=user_in_base.id, id_for_user=len(users_purchases)+1, date=dt.now().date())
    alfa_cur_session.add(new_purchase)
    alfa_cur_session.commit()

    user_in_base.edit_purchase_id = new_purchase.id
    alfa_u_session.commit()

    cur_types = alfa_cur_session.query(CurrencyTypes).all()

    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.add(*[c_type.abbreviation for c_type in cur_types])
    # markup.add("USD", "EUR")

    msg = bot.send_message(chat_id, "Please choose currency", reply_markup=markup)
    bot.register_next_step_handler(msg, set_currency, new_purchase, cur_types)
    # bot.send_message(chat_id, "Please choose currency type\n/usd\n/eur")  # сделать inline message


def send_edit_keyboard(chat_id, msg_text=''):
    if not msg_text:
        msg_text = 'Choose what you want to edit.\nBy default Date set today, Buy rate set rate for date of purchase, waiting for by default is 0'

    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.add("Value", "Date", "Buy rate", "Waiting for", "Mark as selled", "End editing")
    msg = bot.send_message(chat_id, msg_text, reply_markup=markup)
    return msg


def set_currency(message, new_purchase, cur_types):
    chat_id = message.chat.id
    currency = message.text

    if currency in [c_type.abbreviation for c_type in cur_types]:
        for c_type in cur_types:
            if c_type.abbreviation == currency:
                new_purchase.currency_type = c_type.id
                if not new_purchase.currency_buy_rate:
                    last_rate = alfa_cur_session.query(CurrencyRates).filter(CurrencyRates.currency_type == c_type.id).order_by(
                        CurrencyRates.id)[-1]
                    new_purchase.currency_buy_rate = last_rate.to_sell
                alfa_cur_session.commit()

                msg = bot.send_message(chat_id, "Write value in format 0.0", reply_markup=types.ReplyKeyboardRemove())
                bot.register_next_step_handler(msg, set_value, new_purchase)

    else:
        bot.send_message(chat_id, "error...")


def set_value(message, new_purchase):
    chat_id = message.chat.id
    value = message.text
    try:
        new_purchase.currency_value = float(value.replace(",", "."))
        alfa_cur_session.commit()

        msg = send_edit_keyboard(chat_id)
        bot.register_next_step_handler(msg, edit_purchase_param, new_purchase)
    except Exception as e:
        bot.send_message(chat_id, "%s!" % str(e))


def edit_purchase_param(message, new_purchase):
    chat_id = message.chat.id
    msg_text = message.text

    if msg_text == "Date":
        msg = bot.send_message(chat_id, "Write date in format dd.mm.yy", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, edit_date, new_purchase)
        # bot.send_message(chat_id, "This function is not work yet", reply_markup=types.ReplyKeyboardRemove())

    elif msg_text == "Value":
        msg = bot.send_message(chat_id, "Write value in format 0.0", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, set_value, new_purchase)
        # bot.send_message(chat_id, "This function is not work yet", reply_markup=types.ReplyKeyboardRemove())

    elif msg_text == "Buy rate":
        msg = bot.send_message(chat_id, "Write rate in format 0.0", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, edit_buy_rate, new_purchase)

    elif msg_text == "Waiting for":
        msg = bot.send_message(chat_id, "Write value in format 0.0", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, edit_waiting_for, new_purchase)
        # bot.send_message(chat_id, "This function is not work yet", reply_markup=types.ReplyKeyboardRemove())

    elif msg_text == "Mark as selled":
        new_purchase.selled = True
        alfa_cur_session.commit()
        bot.send_message(chat_id, "Ok", reply_markup=types.ReplyKeyboardRemove())

    elif msg_text == "End editing":
        bot.send_message(chat_id, "Ok", reply_markup=types.ReplyKeyboardRemove())

    else:
        bot.send_message(chat_id, "Something going wrong", reply_markup=types.ReplyKeyboardRemove())


def edit_buy_rate(message, new_purchase):
    chat_id = message.chat.id
    value = message.text
    try:
        new_purchase.currency_buy_rate = float(value.replace(",", "."))
        alfa_cur_session.commit()

        msg = send_edit_keyboard(chat_id)
        bot.register_next_step_handler(msg, edit_purchase_param, new_purchase)

    except Exception as e:
        bot.send_message(chat_id, "%s!" % str(e))


def edit_waiting_for(message, new_purchase):
    chat_id = message.chat.id
    value = message.text
    try:
        new_purchase.waiting_for = float(value.replace(",", "."))
        alfa_cur_session.commit()

        msg = send_edit_keyboard(chat_id)
        bot.register_next_step_handler(msg, edit_purchase_param, new_purchase)

    except Exception as e:
        bot.send_message(chat_id, "%s!" % str(e))


def edit_date(message, new_purchase):
    chat_id = message.chat.id
    date = message.text
    try:
        try:
            date = dt.strptime(date, "%d.%m.%Y")
        except ValueError:
            date = dt.strptime(date, "%d.%m.%y")

        new_purchase.date = date
        alfa_cur_session.commit()

        msg = send_edit_keyboard(chat_id)
        bot.register_next_step_handler(msg, edit_purchase_param, new_purchase)

    except ValueError:
        bot.send_message(chat_id, "Wrong date format")

    except Exception as e:
        bot.send_message(chat_id, "%s!" % str(e))


@bot.message_handler(commands=['purchased_list'])
@check_user_in_base_dec
def purchased_list(message, user_in_base, page=1):
    chat_id = message.chat.id

    users_purchases = alfa_cur_session.query(PurchasedCurrency).filter(PurchasedCurrency.user_id == user_in_base.id)
    users_not_selled_pur = users_purchases.filter(PurchasedCurrency.selled == False).all()
    # users_purchases = users_purchases.order_by(PurchasedCurrency.date).all()[::-1]
    users_purchases = users_not_selled_pur[::-1] # send only unselled prchsss

    purchased_btns = {}
    if len(users_purchases) > 0:
        msg_text = "You have {count} purchases\nNot selled: {not_selled_count}\n".format(
            count=len(users_purchases),
            not_selled_count=len(users_not_selled_pur),
        )
        if page == 1:
            if len(users_purchases) > 10:
                msg_text = msg_text + "Your last 10 purchases:\n"
            elif len(users_purchases) == 0:
                pass
            else:
                msg_text = msg_text + "Your last {} purchases:\n".format(len(users_purchases))

        cur_types = alfa_cur_session.query(CurrencyTypes).all()
        last_rates = {}
        for cur_type in cur_types:
            last_cur_rate = \
                alfa_cur_session.query(CurrencyRates).filter(CurrencyRates.currency_type == cur_type.id).order_by(
                    CurrencyRates.id)[-1]
            last_rates[cur_type.id] = last_cur_rate.to_buy

        for user_purchase in users_purchases[:10]:

            in_rubs = round(user_purchase.currency_value * last_rates[user_purchase.currency_type])
            rubs_inqlt = round(in_rubs - user_purchase.currency_value * user_purchase.currency_buy_rate)
            rubs_inqlt = ("+" + str(rubs_inqlt) if rubs_inqlt > 0 else rubs_inqlt)
            msg_text = msg_text + "№{id_for_user} {currency} *{value}*\n{date}\nPurchased for {buy_rate}\nIn Rub: {rub} ({inqlt})\n\n".format(
                id_for_user=user_purchase.id_for_user,
                currency=alfa_cur_session.query(CurrencyTypes).get(user_purchase.currency_type).abbreviation,
                value=user_purchase.currency_value,
                date=user_purchase.date.date(),
                buy_rate=user_purchase.currency_buy_rate,
                rub=in_rubs,
                inqlt= rubs_inqlt,
            )
            purchased_btns[user_purchase.id_for_user] = "edit №%d" % user_purchase.id_for_user

        user_sums = {}
        for purchase in users_not_selled_pur:
            # print(purchase.waiting_for, rate.to_buy)
            # if rate.to_buy >= purchase.waiting_for:
            #     can_be_selled.append(purchase)
            try:
                user_sums[purchase.currency_type] += float(purchase.currency_value)
            except KeyError:
                user_sums[purchase.currency_type] = float(purchase.currency_value)

        # user_sums.append(
        #     "{currency} {value} == {rubles}".format(
        #     currency=next((c_type.abbreviation for c_type in cur_types if c_type.id == purchase.currency_type)),
        #     value=user_summ,
        #     rubles=(user_summ*rate.to_buy))
        # )
        msg_text = msg_text + "\nYou have:\n"

        for cur_type, cur_summ in user_sums.items():
            last_cur_rate = \
            alfa_cur_session.query(CurrencyRates).filter(CurrencyRates.currency_type == cur_type).order_by(
                CurrencyRates.id)[-1]

            msg_text = msg_text + "{currency} {value} == RUB {rubles}\n".format(
            currency=alfa_cur_session.query(CurrencyTypes).get(cur_type).abbreviation,
            value=round(cur_summ, 1),
            rubles=round(cur_summ*last_cur_rate.to_buy)
            )


    else:
        msg_text = "You have no one purchase yet"

    if purchased_btns:
        purchased_btns['exit'] = "exit"
        # markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
        # markup.add(*purchased_btns)
        markup = telebot.types.InlineKeyboardMarkup()
        for btn_id, btn_text in purchased_btns.items():
            markup.add(telebot.types.InlineKeyboardButton(text=btn_text, callback_data=btn_id))
        msg = bot.send_message(chat_id, msg_text, reply_markup=markup, parse_mode='Markdown')
        # bot.register_next_step_handler(msg, choose_purchase, user_in_base)
    else:
        bot.send_message(chat_id, msg_text)


# def choose_purchase(message, user_in_base):
#     chat_id = message.chat.id
#     if message.text == "exit":
#         bot.send_message(chat_id, "Ok", reply_markup=types.ReplyKeyboardRemove())

#     else:
#         try:
#             purchase_usr_id = int(message.text.split("№")[1])
#         except IndexError:
#             bot.send_message(chat_id, "Something wrong", reply_markup=types.ReplyKeyboardRemove())

#         try:
#             purchase = alfa_cur_session.query(PurchasedCurrency).\
#                 filter(PurchasedCurrency.user_id == user_in_base.id).\
#                 filter(PurchasedCurrency.id_for_user == purchase_usr_id).first()
#         except InvalidRequestError as e:
#             alfa_cur_session.rollback()
#             purchase = alfa_cur_session.query(PurchasedCurrency).\
#                 filter(PurchasedCurrency.user_id == user_in_base.id).\
#                 filter(PurchasedCurrency.id_for_user == purchase_usr_id).first()

#         msg_text = "№{id_for_user} {currency} {value}\nDate: {date}\nPurchased for {buy_rate}\nWaiting: {waiting}\n{selled}\n\nWant edit?".format(
#                     id_for_user=purchase.id_for_user,
#                     currency=alfa_cur_session.query(CurrencyTypes).get(purchase.currency_type).abbreviation,
#                     value=purchase.currency_value,
#                     date=purchase.date.date(),
#                     buy_rate=purchase.currency_buy_rate,
#                     waiting=purchase.waiting_for,
#                     selled=("Selled" if purchase.selled else "Not selled")
#                 )
#         msg = send_edit_keyboard(chat_id, msg_text)
#         bot.register_next_step_handler(msg, edit_purchase_param, purchase)


@bot.callback_query_handler(func=lambda call: True)
@check_user_in_base_dec
def choose_purchase(call, user_in_base):
    if call.data == 'exit':
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(callback_query_id=call.id, text='Closed')
    else:
        chat_id = call.message.chat.id
        try:
            purchase_usr_id = int(call.data)
        except IndexError:
            bot.answer_callback_query(callback_query_id=call.id, text='Something wrong')

        try:
            purchase = alfa_cur_session.query(PurchasedCurrency).\
                filter(PurchasedCurrency.user_id == user_in_base.id).\
                filter(PurchasedCurrency.id_for_user == purchase_usr_id).first()
        except InvalidRequestError as e:
            alfa_cur_session.rollback()
            purchase = alfa_cur_session.query(PurchasedCurrency).\
                filter(PurchasedCurrency.user_id == user_in_base.id).\
                filter(PurchasedCurrency.id_for_user == purchase_usr_id).first()

        msg_text = "№{id_for_user} {currency} {value}\nDate: {date}\nPurchased for {buy_rate}\nWaiting: {waiting}\n{selled}\n\nWant edit?".format(
                    id_for_user=purchase.id_for_user,
                    currency=alfa_cur_session.query(CurrencyTypes).get(purchase.currency_type).abbreviation,
                    value=purchase.currency_value,
                    date=purchase.date.date(),
                    buy_rate=purchase.currency_buy_rate,
                    waiting=purchase.waiting_for,
                    selled=("Selled" if purchase.selled else "Not selled")
                )
        msg = send_edit_keyboard(chat_id, msg_text)
        bot.register_next_step_handler(msg, edit_purchase_param, purchase)



# @bot.message_handler(func=lambda message: True)
# def forward(message):
#     id = 1930767

#     msg = "from: [_{}_](tg://user?id={})\n{}".format(message.chat.username, message.chat.id, message.text)

#     bot.send_message(id, msg, parse_mode='Markdown')


# @bot.message_handler(commands=['usd'])
# @check_user_in_base_dec
# def set_currency(message, user_in_base):
#     chat_id = message.chat.id
#
#     purchase_id = user_in_base.edit_purchase_id
#     if purchase_id:
#         purchase = alfa_cur_session.query(PurchasedCurrency).get(purchase_id)
#         cur_types = alfa_cur_session.query(CurrencyTypes).all()
#         for c_type in cur_types:
#             if c_type.abbreviation.lower() == 'usd':
#                 cur_type_id = c_type.id


# @bot.message_handler(func=lambda message: True, content_types=['text'])
# @check_user_in_base_dec
# def text_message(message, user_in_base):
#     chat_id = message.chat.id
#     username = message.chat.username
#
#     if user_in_base.wait_cur_type and message.text is string:
#
#         alfa_cur_session.add(PurchasedCurrency(currency_type_id, currency_value=0, date=dt.now(), user_id)
#         alfa_cur_session.commit()
#     if user_in_base.wait_cur_value and message is float:
#         buyed_cur = alfa_cur_session.query(PurchasedCurrency).filter(PurchasedCurrency.user_id == user_id).filter(PurchasedCurrency.value == 0).first()
#         buyed_cur.value = float(message.text)
#         alfa_cur_session.commit()
#
#
#
#
#
# @bot(command=["buyed_list"])
# def buyed_list(message):
#     user_id = message.chat.id
#     # buyed_currencies = cur_session.query(PurchasedCurrency).filter(PurchasedCurrency.user_id == user_id)
#     # make inline_message with pagination


if __name__ == "__main__":

    bot.remove_webhook()
    # Enable saving next step handlers to file "./.handlers-saves/step.save".
    # Delay=2 means that after any change in next step handlers (e.g. calling register_next_step_handler())
    # saving will hapen after delay 2 seconds.
    bot.enable_save_next_step_handlers(delay=2)

    # Load next_step_handlers from save file (default "./.handlers-saves/step.save")
    # WARNING It will work only if enable_save_next_step_handlers was called!
    bot.load_next_step_handlers()

    print('start polling')
    bot.polling()
