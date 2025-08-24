# bib-lib

## Usage

* Build venv using Python 3. 

* Open Pycharm project and run files from main. 

* Run `parser.py` to generate `.csv`s from existing `.bib`s.

* If more than one `.csv` is created, run `load_all_csv.py` to concat them into one `.csv`. Manually check if needed. 
  * Delete `combined.csv` if it exists. 
  * Manually edit `combined.csv` as needed.

* Run `write_all.py` on `combined.csv` to create a new master `lib.bib-YYYY-MM-DD-HHMM.bib`.
  * Delete existing `lib.bib-YYYY-MM-DD-HHMM.bib`.

* Update `README.md`.

## Notes

* Current master `.bib`: [bib_files/lib-2025-08-24_1113.bib](bib_files/lib-2025-08-24_1113.bib)

* Current master CSV as Google Sheet: [https://docs.google.com/spreadsheets/d/1vKpf7s-Swz4bGy4786QdOwmtu64CZ81LrOmjx1eLwco/edit](https://docs.google.com/spreadsheets/d/1vKpf7s-Swz4bGy4786QdOwmtu64CZ81LrOmjx1eLwco/edit)




