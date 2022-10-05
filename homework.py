import datetime
import json
import logging
import os
import time
import requests
import telegram
import sys
from http import HTTPStatus


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler()
)


class TheAnswerIsNot200Error(Exception):
    """Ответ сервера не равен 200."""


class EmptyDictionaryOrListError(Exception):
    """Пустой словарь или список."""


class UndocumentedStatusError(Exception):
    """Недокументированный статус."""


class RequestExceptionError(Exception):
    """Ошибка запроса."""


def send_message(bot, message):
    """Функция для отправки сообщения."""
    logger.info(
        f'Сообщение в Telegram подготовлено к отправке: {message}')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)

    except telegram.TelegramError as telegram_error:
        raise Exception(telegram_error)
    else:
        logger.info(
            f'Сообщение в Telegram отправлено: {message}')


def get_api_answer(current_timestamp):
    """Получение ответа через API."""
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    payload = {'from_date': current_timestamp}
    try:
        response = requests.get(ENDPOINT, headers=headers, params=payload)
        if response.status_code != HTTPStatus.OK:
            code_api_msg = (
                f'Эндпоинт {ENDPOINT} недоступен.'
                f' Код ответа API: {response.status_code}')
            raise TheAnswerIsNot200Error(code_api_msg)
        return response.json()
    except requests.exceptions.RequestException as request_error:
        code_api_msg = f'Код ответа API (RequestException): {request_error}'
        raise RequestExceptionError(code_api_msg) from request_error
    except json.JSONDecodeError as value_error:
        code_api_msg = f'Код ответа API (ValueError): {value_error}'
        raise json.JSONDecodeError(code_api_msg) from value_error


def check_response(response):
    """Проверка ответа."""
    if not isinstance(response, dict):
        error_message = 'Не верный тип ответа API'
        raise TypeError(error_message)
    if 'homeworks' not in response:
        error_message = 'Ключ homeworks отсутствует'
        raise KeyError(error_message)
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        error_message = 'homeworks не является списком'
        raise TypeError(error_message)
    if len(homeworks) == 0:
        error_message = 'Пустой список домашних работ'
        raise ValueError(error_message)
    homework = homeworks[0]
    return homework


def parse_status(homework):
    """Получение и проверка статуса. 105-107 нельзя удалять иначе ошибка get"""
    if 'homework_name' not in homework:
        error_message = 'Ключ homework_name отсутствует'
        raise KeyError(error_message)
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status is None:
        error_message = 'Ключ homework_status отсутствует'
        raise Exception(error_message)
    if homework_status not in HOMEWORK_STATUSES:
        error_message = 'Неизвестный статус домашней работы'
        raise Exception(error_message)
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def extracted_from_parse_status(arg0, arg1):
    """Получение статуса из аргументов."""
    code_api_msg = f'{arg0}{arg1}'
    logger.error(code_api_msg)
    raise UndocumentedStatusError(code_api_msg)


def check_tokens():
    """Проверка токенов."""
    return(all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]))


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.error('Переменные отсутствуют в ENV')
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    now = datetime.datetime.now()
    send_message(
        bot,
        f'Я начал свою работу: {now.strftime("%d-%m-%Y %H:%M")}')
    current_timestamp = int(time.time())
    tmp_status = 'reviewing'
    errors = True
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework and tmp_status != homework['status']:
                message = parse_status(homework)
                send_message(bot, message)
                tmp_status = homework['status']
            logger.info(
                'Изменений нет, ждем 10 минут и проверяем API')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if errors:
                errors = False
                send_message(bot, message)
            logger.critical(message)

        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
