"""
Helper script to push SmartResolve AI to GitHub using a Personal Access Token.
"""

import subprocess
import getpass
import sys

def main():
    print("=" * 60)
    print("🚀 Push SmartResolve AI to https://github.com/navyad-a/smartresolve-ai")
    print("=" * 60)
    print("\nGitHub requires authentication to push to your repository.")
    print("You can generate a token at: https://github.com/settings/tokens (classic token with 'repo' scope)\n")
    
    token = input("Paste your GitHub Personal Access Token (or press Enter to cancel): ").strip()
    if not token:
        print("❌ Push cancelled.")
        sys.exit(0)
        
    remote_url = f"https://navyad-a:{token}@github.com/navyad-a/smartresolve-ai.git"
    git_cmd = r"C:\Users\Navya shree\.gemini\antigravity\scratch\mingit\cmd\git.exe"
    
    print("\n⏳ Pushing code to GitHub...")
    try:
        res = subprocess.run([git_cmd, "push", remote_url, "main", "--force"], capture_output=True, text=True)
        if res.returncode == 0:
            print("\n🎉 SUCCESS! All files, tests, and documentation have been pushed to:")
            print("👉 https://github.com/navyad-a/smartresolve-ai")
        else:
            print("\n❌ Error pushing to GitHub:")
            print(res.stderr)
    except Exception as e:
        print(f"\n❌ Execution error: {e}")

if __name__ == "__main__":
    main()
