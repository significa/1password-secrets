import json
import subprocess
from datetime import datetime
from io import StringIO

from dotenv import dotenv_values
from sgqlc.endpoint.http import HTTPEndpoint

FLY_GRAPHQL_ENDPOINT = "https://api.fly.io/graphql"


def get_1password_env_file_item_id(app_id):
    secure_notes = json.loads(
        subprocess.check_output(
            ['op', 'item', 'list', '--categories',
                'Secure Note', '--format', 'json']
        )
    )

    return next(
        (
            item['id']
            for item in secure_notes
            if f'fly.{app_id}' in item['title']
        ),
        None
    )


def get_envs_from_1password(item_id):
    item = json.loads(
        subprocess.check_output(
            ['op', 'item', 'get', item_id, '--format', 'json']
        )
    )

    return next(
        field['value']
        for field in item['fields']
        if field['id'] == 'notesPlain'
    )


def get_fly_auth_token():
    return json.loads(
        subprocess.check_output(['fly', 'auth', 'token', '--json'])
    )['token']


def update_fly_secrets(app_id, secrets):
    set_secrets_mutation = """
    mutation(
        $appId: ID!
        $secrets: [SecretInput!]!
        $replaceAll: Boolean!
    ) {
        setSecrets(
            input: {
                appId: $appId
                replaceAll: $replaceAll
                secrets: $secrets
            }
        ) {
            app {
                name
            }
            release {
                version
            }
        }
    }
    """

    secrets_input = [
        {'key':  key, 'value': value}
        for key, value in secrets.items()
    ]
    variables = {
        'appId': app_id,
        'secrets': secrets_input,
        'replaceAll': True
    }

    headers = {'Authorization': f'Bearer {get_fly_auth_token()}'}

    endpoint = HTTPEndpoint(
        FLY_GRAPHQL_ENDPOINT,
        headers
    )

    response = endpoint(
        query=set_secrets_mutation,
        variables=variables
    )

    if response.get('errors') is not None:
        for error in response['errors']:
            print(error['message'])

        raise RuntimeError()
    else:
        print(
            f'Releasing fly app {app_id}'
            f' version {response["data"]["setSecrets"]["release"]["version"]}'
        )


def update_1password_last_updated_secret_field(app_id):
    now = datetime.now()
    now_formatted = now.strftime("%d/%m/%Y %H:%M:%S")

    subprocess.check_output([
        'op',
        'item',
        'edit',
        app_id,
        f'Generated by fly secrets.last updated at[text]={now_formatted}',
        '--format',
        'json'
    ])


def get_secrets_from_envs(input: str):
    return dotenv_values(stream=StringIO(input))


def sync_1password_secrets_to_fly(app_id):
    item_id = get_1password_env_file_item_id(app_id)

    if item_id is None:
        print(f'There is no env file in 1password matching fly.{app_id}')
        raise RuntimeError()

    secrets = get_secrets_from_envs(get_envs_from_1password(item_id))

    update_fly_secrets(app_id, secrets)

    update_1password_last_updated_secret_field(item_id)
