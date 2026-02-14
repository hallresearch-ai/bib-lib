# bib-lib

## Usage

* `git pull origin main`

* Build venv using Python 3. 

* Open IDE and run files from main. 

* Run `parser.py` to generate `.csv`s from existing `.bib`s.

* If more than one `.csv` is created, run `load_all_csv.py` to concat them into one `.csv`. Delete `bib_files/combined.csv` if it exists. 

* Delete existing files in [G-drive](https://drive.google.com/drive/folders/1Mtb5zvrQy7JjtTm1h7wLMCJ1_B93MZC4?usp=drive_link).

* Load combined.csv to [G-drive](https://drive.google.com/drive/folders/1Mtb5zvrQy7JjtTm1h7wLMCJ1_B93MZC4?usp=drive_link).

* Examine/update combined.csv as Google sheet.
  * Reference `bib_files/to_add_update.csv`.
  * Sort by `title`. 
  * Delete and recreate `citation_key`. Formula to create keys: `=CONCAT(LEFT(REGEXREPLACE(AX2, "[^A-Za-z0-9]", ""), 20), TEXT(ROW(AX2)-1, "000"))`
  * Re-sort by `citation_key` for better alphabetization. 
  * Clear out `bib_files/to_add_update.csv`.
  * Delete `bib_files/combined.csv`

* Download combined Google sheet as `bib_files/combined.csv`.

* Run `write_all.py` on `bib_files/combined.csv` to create a new master `lib.bib-YYYY-MM-DD-HHMM.bib`.
  * Move existing `lib.bib-YYYY-MM-DD-HHMM.bib` other files to in `bib_files` to `bib_files/old`.

* Update `Current master` and `Google sheet` in `README.md`.

* Commit to GitHub:
```bash
git add -A .
git commit -m'update for M/DD'
git push origin main
```

* Check links in GitHub.

## Notes

* Current master `.bib`: [bib_files/lib-2026-02-14_1400.bib](bib_files/lib-2026-02-14_1400.bib)

* **WORK WITH WHILE WRITING FOR EFFICIENT SEARCH/SORT** - Current master CSV as Google Sheet: [https://docs.google.com/spreadsheets/d/1RFt7pSHhcXaZN5aSzD22aZbqKeBR4z97TjYkTCKjfZY/edit?usp=sharing](https://docs.google.com/spreadsheets/d/1RFt7pSHhcXaZN5aSzD22aZbqKeBR4z97TjYkTCKjfZY/edit?usp=sharing)
  * Try to use `bib_files/to_add_update.bib` while writing - this will make the update process much smoother. 




