import argparse, sys
from fly_1password_secrets import fly_1password_secrets

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='This is the description.')
    parser.add_argument('app_name', metavar='A', type=str, help='Fly application name')
    args = parser.parse_args()
    app_id = args.app_name

    try:
        fly_1password_secrets.sync_1password_secrets_to_fly(app_id)
    except Exception:
        sys.exit(1)
