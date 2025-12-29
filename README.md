# bib-lib

## Usage

* Build venv using Python 3. 

* Open IDE and run files from main. 

* Run `parser.py` to generate `.csv`s from existing `.bib`s.

* If more than one `.csv` is created, run `load_all_csv.py` to concat them into one `.csv`. Manually check if needed. 
  * Delete `combined.csv` if it exists. 
  * Manually edit `combined.csv` as needed.

* Run `write_all.py` on `combined.csv` to create a new master `lib.bib-YYYY-MM-DD-HHMM.bib`.
  * Move existing `lib.bib-YYYY-MM-DD-HHMM.bib` to `bib_files/old`.

* Update `README.md`.

## Notes

* Current master `.bib`: [bib_files/lib-2025-12-29_1226.bib](bib_files/lib-2025-12-29_1226.bib)

* **WORK WITH WHILE WRITING FOR EFFICIENT SEARCH/SORT** - Current master CSV as Google Sheet: [https://docs.google.com/spreadsheets/d/16EjvC356ua2OwyJalmgAaC2TEAkkKDVkbhzpLXxxNG0/edit](https://docs.google.com/spreadsheets/d/16EjvC356ua2OwyJalmgAaC2TEAkkKDVkbhzpLXxxNG0/edit)
  * Try to use `bib_files/to_add_update.bib` while writing - this will make the update process much smoother. 




