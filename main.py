#!/usr/bin/env python3
"""Lanceur : python main.py [fichier.ork|fichier.rkt|fiche.xml]"""
import sys

from flightcard.app import main

if __name__ == "__main__":
    sys.exit(main())
