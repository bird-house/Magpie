#!/usr/bin/env python3

import argparse
import datetime
import logging
import random
import requests
import string

LOGGER = logging.getLogger(__name__)


def format_response(response):
    response_json = response.json()
    return str(response_json.get('code')) + ' : ' + response_json.get('detail')


def create_users(email_list, magpie_url, magpie_admin_user_name, magpie_admin_password):
    session = requests.Session()
    response = session.post(magpie_url + "/signin", data={'user_name': magpie_admin_user_name,
                                                          'password': magpie_admin_password,
                                                          'provider_name': 'ziggurat'})
    if not response.ok:
        LOGGER.error(format_response(response))
        return []

    users = []
    for email in email_list:
        user = {'email': email,
                'user_name': email,
                # generate a password made of 8 random alphanumeric characters
                'password': "".join(random.choice(string.ascii_letters + string.digits) for _ in range(8)),
                'result': ""}
        users.append(user)
        response = session.post(magpie_url + "/users", data={'user_name': user['user_name'],
                                                             'email': user['email'],
                                                             'password': user['password'],
                                                             'group_name': 'users'})
        if not response.ok:
            user['result'] = format_response(response)

    # test each successful users with a login
    for user in users:
        if user['result'] == "":
            session = requests.Session()
            response = session.post(magpie_url + "/signin",
                                    data={'user_name': user['user_name'], 'password': user['password'],
                                          'provider_name': 'ziggurat'})
            user['result'] = format_response(response)
    return users


def delete_users(user_names, magpie_url, magpie_admin_user_name, magpie_admin_password):
    session = requests.Session()
    response = session.post(magpie_url + "/signin", data={'user_name': magpie_admin_user_name,
                                                          'password': magpie_admin_password,
                                                          'provider_name': 'ziggurat'})
    if not response.ok:
        LOGGER.error(format_response(response))
        return

    users = []
    for user in user_names:
        response = session.delete(magpie_url + "/users/" + user)
        users.append({'user_name': user, 'result': format_response(response)})
    return users


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create users on Magpie')
    parser.add_argument('url', help='url used to access the magpie service')
    parser.add_argument('user_name', help='admin username for magpie login')
    parser.add_argument('password', help='admin password for magpie login')
    parser.add_argument('emails', nargs='*', help='list of emails for users to be created')
    args = parser.parse_args()

    LOGGER.setLevel(logging.DEBUG)
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

    users = create_users(args.emails, args.url, args.user_name, args.password)

    if len(users) == 0:
        LOGGER.warning("No users to create")
    else:
        COLUMN_SIZE = 60
        output = "\nUSERNAME".ljust(COLUMN_SIZE) + "PASSWORD".ljust(COLUMN_SIZE) + "RESULT".ljust(COLUMN_SIZE) + "\n"
        output += "".ljust(COLUMN_SIZE * 3, "_") + "\n\n"
        for user in users:
            output += user['user_name'].ljust(COLUMN_SIZE) + user['password'].ljust(COLUMN_SIZE) + user['result'].ljust(
                COLUMN_SIZE) + "\n"

        LOGGER.info(output)

        filename = "createUsers_log__" + datetime.datetime.now().strftime('%Y%m%d__%H%M%S') + ".txt"
        with open(filename, "w+") as file:
            file.write(output)
            LOGGER.info("Output results sent to " + filename)
