import sqlite3
import csv

with sqlite3.connect("songdata.db") as con:
	print()