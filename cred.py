import json
import os
import subprocess
import sys
import time

def load_credentials_and_test(json_file="credentialsAWS.json"):
    if not os.path.exists(json_file):
        print(f"❌ Error: {json_file} not found.")
        sys.exit(1)

    with open(json_file, "r", encoding="utf-8") as f:
        creds = json.load(f)

    # --- 1. Set variables for the CURRENT session/script's environment ---
    os.environ['AWS_ACCESS_KEY_ID'] = creds['AccessKeyId']
    os.environ['AWS_SECRET_ACCESS_KEY'] = creds['SecretAccessKey']
    if 'SessionToken' in creds and creds['SessionToken']:
        os.environ['AWS_SESSION_TOKEN'] = creds['SessionToken']
    os.environ['AWS_DEFAULT_REGION'] = creds['Region']
    
    print("✅ Environment variables set for the current Python session.")

    # --- 2. Permanently add variables to ~/.bashrc ---
    bashrc_path = os.path.expanduser("~/.bashrc")
    print(f"📄 Updating {bashrc_path} for future sessions.")
    
    with open(bashrc_path, "a", encoding="utf-8") as f:
        f.write(f"\n# Added by script on {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"export AWS_ACCESS_KEY_ID='{creds['AccessKeyId']}'\n")
        f.write(f"export AWS_SECRET_ACCESS_KEY='{creds['SecretAccessKey']}'\n")
        if 'SessionToken' in creds and creds['SessionToken']:
            f.write(f"export AWS_SESSION_TOKEN='{creds['SessionToken']}'\n")
        f.write(f"export AWS_DEFAULT_REGION='{creds['Region']}'\n")
    
    print("💡 Run 'source ~/.bashrc' in your terminal to apply changes immediately.")

    # --- 3. Test connection using the current script's environment variables ---
    print("\n📡 Testing connection within current process (via 'aws sts get-caller-identity')...")
    # We use subprocess to run the actual 'aws' command in the modified env
    result = subprocess.run(
        ["aws", "sts", "get-caller-identity"],
        capture_output=True,
        text=True,
        env=os.environ,
        check=False,
    )

    if result.returncode == 0:
        print("✅ Connection Test Succeeded!")
        print(result.stdout)
    else:
        print(f"❌ Connection Test Failed: {result.stderr}")


if __name__ == "__main__":
    load_credentials_and_test()
