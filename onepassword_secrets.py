import argparse
import json
import logging
import re
import subprocess
import sys
from datetime import datetime
from io import StringIO
from tempfile import NamedTemporaryFile

from dotenv import dotenv_values
from sgqlc.endpoint.http import HTTPEndpoint

FLY_GRAPHQL_ENDPOINT = 'https://api.fly.io/graphql'
DATE_FORMAT = '%Y/%m/%d %H:%M:%S'
DEFAULT_ENV_FILE_NAME = '.env'


class UserError(RuntimeError):
    pass


def _setup_logger():
    class Formatter(logging.Formatter):
        def format(self, record):
            if record.levelno == logging.INFO:
                self._style._fmt = "%(message)s"
            else:
                self._style._fmt = "%(levelname)s: %(message)s"
            return super().format(record)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(Formatter())
    logger.addHandler(stdout_handler)

    return logger


logger = _setup_logger()


def get_1password_env_file_item_id(title_substring):
    secure_notes = json.loads(
        subprocess.check_output(
            [
                'op',
                'item',
                'list',
                '--categories',
                'Secure Note',
                '--format',
                'json',
            ]
        )
    )

    item_ids = list(
        item['id']
        for item in secure_notes
        if title_substring in item['title'].split(' ')
    )

    if len(item_ids) == 0:
        raise_error(
            f'No 1password secure note found with a name containing {title_substring!r}'
        )

    if len(item_ids) > 1:
        raise_error(
            f'Found {len(item_ids)} 1password secure notes with a name containing '
            f'{title_substring!r}, expected one'
        )

    return item_ids[0]


def get_item_from_1password(item_id):
    return json.loads(
        subprocess.check_output(
            ['op', 'item', 'get', item_id, '--format', 'json']
        )
    )


def get_envs_from_1password(item_id):
    item = get_item_from_1password(item_id)

    result = first(
        field.get('value')
        for field in item['fields']
        if field['id'] == 'notesPlain'
    )
    if result is None or result == '':
        raise_error('Empty secrets, aborting')

    return result


def get_filename_from_1password(item_id):
    item = get_item_from_1password(item_id)

    result = first(
        field.get('value')
        for field in item['fields']
        if field['label'] == 'file_name'
    )

    return result


def get_fly_auth_token():
    return json.loads(
        subprocess.check_output(['fly', 'auth', 'token', '--json'])
    )['token']


def _get_file_contents(filepath, raise_if_not_found=True):
    try:
        with open(filepath, 'r') as file:
            return file.read()
    except FileNotFoundError:
        if raise_if_not_found:
            raise_error(f'Env file {filepath!r} not found!')

        return None


def _boolean_prompt(prompt: str):
    user_input = ''
    while user_input not in ['y', 'n']:
        user_input = input(f'{prompt} (y/n): ').lower()

    return user_input == 'y'


def _make_fly_graphql_request(graphql_query, variables):
    headers = {'Authorization': f'Bearer {get_fly_auth_token()}'}

    endpoint = HTTPEndpoint(
        FLY_GRAPHQL_ENDPOINT,
        headers
    )

    response = endpoint(
        query=graphql_query,
        variables=variables
    )

    logger.debug(
        'Fly request:\n{}\n{}\n\nFly response:\n{}\n'.format(
            graphql_query,
            json.dumps(variables, indent=2),
            json.dumps(response, indent=2),
        )
    )

    if response.get('errors') is not None:
        raise_error(
            json.dumps(response['errors'][0])
        )

    return response['data']


def update_fly_secrets(app_id, secrets):
    secrets_input = [
        {'key':  key, 'value': value}
        for key, value in secrets.items()
    ]

    last_update_secrets_response = _make_fly_graphql_request(
        '''
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
        ''',
        {
            'appId': app_id,
            'secrets': secrets_input,
            'replaceAll': True
        },
    )

    get_secrets_response = _make_fly_graphql_request(
        '''
        query(
            $appName: String
        ) {
            app(name: $appName){
                secrets{
                name
                }
            }
        }
        ''',
        {
            'appName': app_id,
        },
    )

    secrets_names_in_env_file = set(secrets.keys())
    secret_names_in_fly = set(
        secret['name']
        for secret in get_secrets_response['app']['secrets']
    )

    secrets_names_in_fly_only = secret_names_in_fly.difference(secrets_names_in_env_file)

    if (
        len(secrets_names_in_fly_only) > 0
        and _boolean_prompt(
            'The following secrets will be deleted from Fly: {}, Are you sure?'.format(
                ", ".join(secrets_names_in_fly_only)
            )
        )
    ):
        last_update_secrets_response = _make_fly_graphql_request(
            '''
            mutation(
                $appId: ID!
                $secretNames: [String!]!
            ) {
                unsetSecrets(
                    input: {
                        appId: $appId
                        keys: $secretNames
                    }
                ){
                        release{
                    id
                    }
                }
            }
            ''',
            {
                'appId': app_id,
                'secretNames': list(secrets_names_in_fly_only),
            },
        )

    release = last_update_secrets_response.get('setSecrets', {}).get('release', None)

    if release:
        release_version = release.get('version', 'unknown')
        print('Releasing fly app {} version {}'.format(app_id, release_version))
    else:
        print(
            'Fly secrets updated, no release created, '
            'make sure to trigger a re-deploy for the changes to apply.'
        )


def _prompt_secret_diff(previous_raw_secrets, new_raw_secrets):
    previous_parsed_secrets = get_secrets_from_envs(previous_raw_secrets)
    new_parsed_secrets = get_secrets_from_envs(new_raw_secrets)

    previous_keys = set(previous_parsed_secrets.keys())
    new_keys = set(new_parsed_secrets.keys())

    deleted_keys = previous_keys.difference(new_keys)
    added_keys = new_keys.difference(previous_keys)
    keys_whos_value_changed = [
        key
        for key in previous_keys.intersection(new_keys)
        if previous_parsed_secrets[key] != new_parsed_secrets[key]
    ]

    if (
        len(deleted_keys) == 0
        and len(added_keys) == 0
        and len(keys_whos_value_changed) == 0
    ):
        if not _boolean_prompt('No changes detected, proceed?'):
            raise_error('Aborted by user')
        return

    elif not _boolean_prompt(
        'Change summary\n{}\nProceed?'.format(
            "\n".join(
                ' {}: {}'.format(label, ', '.join(items))
                for label, items in {
                    'Deleted': deleted_keys,
                    'Added': added_keys,
                    'Modified': keys_whos_value_changed,
                }.items()
                if len(items) != 0
            )
        )
    ):
        raise_error('Aborted by user')


def update_1password_secrets(
    item_id,
    new_raw_secrets,
    previous_raw_secrets=None
):
    if previous_raw_secrets is None:
        previous_raw_secrets = get_envs_from_1password(item_id)

    _prompt_secret_diff(
        previous_raw_secrets=previous_raw_secrets,
        new_raw_secrets=new_raw_secrets,
    )

    logger.debug(f'Updating 1password secret note content for item {item_id!r}')
    subprocess.check_output([
        'op',
        'item',
        'edit',
        item_id,
        f'notesPlain={new_raw_secrets}'
    ])


def update_1password_custom_field(item_id, field, value):
    logger.debug(f'Updating 1password custom field for item {item_id!r}')
    subprocess.check_output([
        'op',
        'item',
        'edit',
        item_id,
        f'Generated by 1password-secrets.{field}[text]={value}',
        '--format',
        'json'
    ])


def get_secrets_from_envs(input: str):
    secrets = dotenv_values(stream=StringIO(input))

    keys_with_values_null_values = [
        key
        for key, value in secrets.items()
        if value is None
    ]

    if len(keys_with_values_null_values) > 0:
        raise_error(
            'Failed to parse env file, values for the following keys are null: {}'.format(
                ", ".join(keys_with_values_null_values)
            )
        )

    return secrets


def import_1password_secrets_to_fly(app_id):
    item_id = get_1password_env_file_item_id(f'fly:{app_id}')

    secrets = get_secrets_from_envs(get_envs_from_1password(item_id))

    logger.debug(f'Secrets loaded from env: {json.dumps(secrets, indent=2)}\n')

    update_fly_secrets(app_id, secrets)

    now_formatted = datetime.now().strftime(DATE_FORMAT)
    update_1password_custom_field(
        item_id,
        'last imported at',
        now_formatted
    )


def edit_1password_fly_secrets(app_id):
    item_id = get_1password_env_file_item_id(f'fly:{app_id}')

    current_raw_secrets = get_envs_from_1password(item_id)

    with NamedTemporaryFile('w+') as file:
        file.writelines(current_raw_secrets)
        file.flush()
        subprocess.check_output(['code', '--wait', file.name])

        file.seek(0)
        new_raw_secrets = file.read()

    update_1password_secrets(
        item_id,
        new_raw_secrets=new_raw_secrets,
        previous_raw_secrets=current_raw_secrets
    )

    now_formatted = datetime.now().strftime(DATE_FORMAT)
    update_1password_custom_field(
        item_id,
        'last edited at',
        now_formatted
    )

    if _boolean_prompt(
        'Secrets updated in 1password, '
        f'do you wish to import secrets to the fly app {app_id}?'
    ):
        import_1password_secrets_to_fly(app_id)


def pull_local_secrets():
    repository = get_git_repository_name_from_current_directory()
    item_id = get_1password_env_file_item_id(f'repo:{repository}')

    secrets = get_envs_from_1password(item_id)

    env_file_name = get_filename_from_1password(item_id) or DEFAULT_ENV_FILE_NAME

    previous_raw_secrets = _get_file_contents(env_file_name, raise_if_not_found=False)

    if previous_raw_secrets:
        _prompt_secret_diff(
            previous_raw_secrets=previous_raw_secrets,
            new_raw_secrets=secrets,
        )

    with open(env_file_name, 'w') as file:
        file.writelines(secrets)

    print(f'Successfully updated {env_file_name} from 1password')


def push_local_secrets():
    repository_name = get_git_repository_name_from_current_directory()
    item_id = get_1password_env_file_item_id(f'repo:{repository_name}')

    env_file_name = get_filename_from_1password(item_id) or DEFAULT_ENV_FILE_NAME

    secrets = _get_file_contents(env_file_name, raise_if_not_found=True)

    update_1password_secrets(item_id, secrets)

    now_formatted = datetime.now().strftime(DATE_FORMAT)
    update_1password_custom_field(
        item_id,
        'last edited at',
        now_formatted
    )

    print(f'Successfully pushed secrets from {env_file_name} to 1password')


def get_git_repository_name_from_current_directory():
    GIT_REPOSITORY_REGEX = r'^(https|git)(:\/\/|@)([^\/:]+)[\/:]([^\/:]+)\/(.+).git$'

    try:
        git_remote_origin_url = subprocess.check_output([
            'git',
            'config',
            '--get',
            'remote.origin.url'
        ]).decode('utf-8')
    except subprocess.CalledProcessError:
        raise_error('Either not in a git repository or remote "origin" is not set')

    regex_match = re.match(
        GIT_REPOSITORY_REGEX,
        git_remote_origin_url
    )

    if regex_match is None:
        raise_error('Could not get remote "origin" url from git repository')

    repository_name = f'{regex_match.group(4)}/{regex_match.group(5)}'

    return repository_name


def raise_error(message):
    print(message)
    raise UserError(message)


def first(iterable):
    try:
        return next(iterable)
    except StopIteration:
        return None


def main():
    parser = argparse.ArgumentParser(
        description='1password-secrets is a set of utilities to sync 1Password secrets.'
    )
    parser.add_argument(
        '--debug',
        action=argparse.BooleanOptionalAction,
        type=bool,
        default=False,
        help='run in debug mode',
    )

    subparsers = parser.add_subparsers(dest='subcommand', required=True)

    fly_parser = subparsers.add_parser('fly', help='manage fly secrets')
    fly_parser.add_argument('action', type=str, choices=['import', 'edit'])
    fly_parser.add_argument('app_name', type=str, help='fly application name')

    local_parser = subparsers.add_parser('local', help='manage local secrets')
    local_parser.add_argument('action', type=str, choices=['pull', 'push'])

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    try:
        if args.subcommand == 'fly':
            if args.action == 'import':
                import_1password_secrets_to_fly(args.app_name)
            elif args.action == 'edit':
                edit_1password_fly_secrets(args.app_name)
        elif args.subcommand == 'local':
            if args.action == 'pull':
                pull_local_secrets()
            elif args.action == 'push':
                push_local_secrets()
    except UserError:
        sys.exit(1)


if __name__ == '__main__':
    main()
