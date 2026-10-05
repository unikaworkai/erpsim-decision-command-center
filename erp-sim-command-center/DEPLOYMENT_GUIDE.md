# Put the app online

This project now has a Streamlit entry point: `streamlit_app.py`. Streamlit Community Cloud will run that file and give you a public link for your professor.

## Before you upload

The project includes the starter Excel reports in `data/baseline/` so the public app opens with the Round 9 example ready. Keep the GitHub repository **private**. The website can still be public while the repository stays private.

Do not upload passwords, API keys, SAP credentials, or files with personal information.

### Make the existing GitHub repository private

Your `unikaworkai/erpsim-decision-command-center` repository currently contains only a starter README. Before copying the project files there:

1. Open https://github.com/unikaworkai/erpsim-decision-command-center.
2. Click **Settings** in the repository navigation. If it is hidden, open the **More** menu first.
3. Click **General** if it is not already selected.
4. Scroll to the very bottom, to **Danger Zone**.
5. Find **Change repository visibility** and click **Change visibility**.
6. Choose **Make private**.
7. Follow GitHub’s confirmation steps. It may ask you to type the repository name.

This hides the code and Excel reports. It does not make the future Streamlit website private.

## Copy the project into the existing GitHub repository

GitHub Desktop is the least complicated method because it handles the GitHub sign-in and final upload for you.

1. Install GitHub Desktop from https://desktop.github.com if it is not already installed.
2. Open GitHub Desktop and sign in with the GitHub account that owns `unikaworkai/erpsim-decision-command-center`.
3. Click **File**, then **Clone repository**.
4. Select the **GitHub.com** tab.
5. Choose `unikaworkai/erpsim-decision-command-center`.
6. Choose a simple local path such as `/Users/unikamaharjan/Documents/GitHub` and click **Clone**. GitHub Desktop creates a new copy of the repository inside that location.
7. Open **Terminal** and paste this command. It copies the completed app into the cloned repository, including the hidden deployment files:

   ```bash
   ditto "/Users/unikamaharjan/Documents/Codex/2026-10-04/files-mentioned-by-the-user-o/outputs/erp-sim-command-center" "/Users/unikamaharjan/Documents/GitHub/erpsim-decision-command-center"
   ```

8. Return to GitHub Desktop. It will show the app files as changes.
9. In the lower-left corner, enter this summary: `Add Streamlit deployment version`.
10. Click **Commit to main**.
11. Click **Push origin** at the top of GitHub Desktop.

If you chose a different folder in step 6, change the final path in the Terminal command to that actual cloned folder. Do not copy files directly through the GitHub web upload page because it can accidentally miss the hidden `.streamlit` and `.gitignore` files.

The project folder you copy from is:

   `/Users/unikamaharjan/Documents/Codex/2026-10-04/files-mentioned-by-the-user-o/outputs/erp-sim-command-center`

## Turn the code into a public website

1. Visit https://share.streamlit.io.
2. Click **Continue to sign in**, then choose **Continue with GitHub**.
3. Allow Streamlit to read the private repository when GitHub asks. It needs read access to build the app.
4. In Streamlit, click **Create app**.
5. Choose **Yup, I have an app**.
6. Complete the fields:

   | Field | Enter this |
   |---|---|
   | Repository | `unikaworkai/erpsim-decision-command-center` |
   | Branch | `main` |
   | Main file path | `streamlit_app.py` |
   | App URL | `erpsim-command-center-unika` or another available simple name |

7. Click **Advanced settings** and select Python 3.12 if Streamlit asks. The app dependencies are already listed in `requirements.txt`.
8. Do not add any secrets. This app does not need them.
9. Click **Deploy**.
10. Wait for Streamlit to show **Your app is live**. Copy the `https://...streamlit.app` address.

## Test the professor link

1. Open a private or incognito browser window.
2. Paste the `https://...streamlit.app` link.
3. Confirm that the Round 9 dashboard opens without a GitHub or Streamlit login.
4. Click **Final round plan**, **Forecast + MRP**, **Procurement**, **Stock transfer**, **Pricing**, **Finance + valuation**, and **Data center**.
5. Download the decision sheet once to confirm downloads work.
6. Send your professor only the `https://...streamlit.app` link.

## Make a change later

1. Edit a project file on your computer.
2. Open GitHub Desktop.
3. Review the changed file list.
4. Write a short summary, such as `Refresh round 10 reports`.
5. Click **Commit to main**.
6. Click **Push origin**.
7. Wait for Streamlit to rebuild. Refresh the public link after a few minutes.

## If something fails

- **Streamlit cannot find the file:** check that the main file path is exactly `streamlit_app.py`.
- **Streamlit says a library is missing:** make sure `requirements.txt` was committed and pushed.
- **The page opens but reports no data:** make sure the `data/baseline/` folder was included when you committed the project.
- **Professor is asked to sign in:** use the app menu in Streamlit Community Cloud and change the app sharing setting to public. Do not change the GitHub source repository to public just to solve this.
- **New report upload disappears after refreshing the page:** that is expected. The public app deliberately treats uploads as temporary for the active browser session. Update the bundled baseline reports through GitHub when you want permanent starter data.
