import email, smtplib, ssl

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
import json


def get_credentials():
    with open("credentials.json", 'r') as credentials:
        credential_obj = json.load(credentials)
        username = credential_obj['username']
        password = credential_obj['password']
        return username, password


def get_element_hash(element):
    if isinstance(element, list):
        el_hash = get_list_hash(element)
    elif isinstance(element, dict):
        el_hash = get_dict_hash(element)
    else:
        el_hash = hash(element)
    return el_hash


def get_dict_hash(element):
    hash_list = []
    for key in element.keys():
        key_hash = hash(key)
        el = element[key]
        el_hash = get_element_hash(el)
        hash_list.append(key_hash + el_hash)
    return sum(hash_list)


def get_list_hash(element):
    hash_list = []
    for el in element:
        el_hash = get_element_hash(el)
        hash_list.append(el_hash)
    return sum(hash_list)


def look_for_repeating(options):
    hash_list = set()
    if isinstance(options, list):
        for el in options:
            el_hash = get_element_hash(el)
            hash_list.add(el_hash)
    elif isinstance(options, dict):
        for key in options.keys():
            key_hash = hash(key)
            el = options[key]
            el_hash = get_element_hash(el)
            hash_list.add(key_hash + el_hash)
    else:
        return False
    return len(options) != len(hash_list)


def get_reciever_list():
    with open('recipient.json', 'r') as reciever_list_json:
        rec_list = json.load(reciever_list_json)
        return rec_list


def send_email_to_recipient(filename, blocks):
    username, password = get_credentials()

    subject = "Listado de bloques con opciones repetidas"
    body = f'Cantidad de bloques con opciones repetidas: {len(blocks.keys())}\n' \
           f'A continuación, un listado con los IDs que tienen problemas, adjunto está un json con más detalles: \n' \
           f'' + '\n'.join(blocks.keys())
    sender_email = username
    receiver_email = get_reciever_list()

    message = MIMEMultipart()
    message["From"] = sender_email
    message["Subject"] = subject

    message.attach(MIMEText(body, "plain"))

    with open(filename, "rb") as attachment:
        # Add file as application/octet-stream
        # Email client can usually download this automatically as attachment
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())

    # Encode file in ASCII characters to send by email
    encoders.encode_base64(part)

    # Add header as key/value pair to attachment part
    part.add_header(
        "Content-Disposition",
        f"attachment; filename= {filename}",
    )

    # Add attachment to message and convert message to string
    message.attach(part)
    text = message.as_string()

    context = ssl.create_default_context()

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        print(f'sender_email: {sender_email}, password: {password}')
        server.login(sender_email, password)
        for receiver in receiver_email:
            server.sendmail(sender_email, receiver, text)


def check_all_blocks(quantity, amount):
    result_filename = 'res.json'
    excluded_blocks_filename = 'excluded_blocks.json'

    get_blocks_url = 'http://production-backend.us-east-1.elasticbeanstalk.com/api/v1/blocks'

    all_blocks_json = requests.get(get_blocks_url).text

    production_host = 'http://production-backend.us-east-1.elasticbeanstalk.com'

    block_list = json.loads(all_blocks_json)

    get_block_detail_url = '{0}/development/blocks/{1}/exercises?quantity={2}'

    block_ret = {}
    index = 0
    excluded_blocks = []
    with open(excluded_blocks_filename, 'r') as file:
        excluded_blocks = json.load(file)
    for i in block_list:
        index += 1
        cur_block_id = i['id']
        if cur_block_id in excluded_blocks:
            continue

        print(f'{index} / {len(block_list)} ----------- {cur_block_id}')
        if cur_block_id == '':
            continue

        headers = {
            'content-type': 'application/json',
            'Accept': 'application/json'
        }
        try:
            t = requests.get(
                get_block_detail_url.format(
                    production_host,
                    cur_block_id,
                    quantity
                ),
                headers=headers,
                timeout=10
            ).text
        except requests.exceptions.ReadTimeout:
            print('This block spent too much time to respond.')
            continue

        try:
            block_data = json.loads(t)
        except json.decoder.JSONDecodeError:
            print('This is not a valid json format.')
            continue

        for individual_block in block_data:
            if 'options' in individual_block:
                has_repeating = look_for_repeating(individual_block['options'])
                if has_repeating:
                    if cur_block_id in block_ret:
                        block_ret[cur_block_id].append(individual_block)
                    else:
                        block_ret[cur_block_id] = [individual_block]
    with open(result_filename, 'w+') as file:
        json.dump(block_ret, file)

    send_email_to_recipient(result_filename, block_ret)


if __name__ == "__main__":
    check_all_blocks(10, 10)
