#!/usr/bin/env python3
"""
Beowulf fitt boundaries and line numbering constants.

This module contains the fitt boundaries and line number markers
for the Beowulf text, following the heorot.dk numbering system.
"""

from typing import Dict, List, Tuple, Final, TypedDict

# Fitt boundaries: (start_line, end_line, fitt_name)
# Note: Fitt 24 doesn't exist in Beowulf, but is included for easier calculations
# The Roman numerals are from the heorot.dk numbering system which follows the 
# MS's. 
FITT_BOUNDARIES: Final[List[Tuple[int, int, str]]] = [
    (1, 52, 'Prologue'),  # prologue
    (53, 114, 'I'),  # 1
    (115, 188, 'II'),
    (189, 257, 'III'),
    (258, 319, 'IIII'),
    (320, 370, 'V'),  # 5
    (371, 455, 'VI'),
    (456, 498, 'VII'),
    (499, 558, 'VIII'),
    (559, 661, 'VIIII'),
    (662, 709, 'X'),  # 10
    (710, 790, 'XI'),
    (791, 836, 'XII'),
    (837, 924, 'XIII'),
    (925, 990, 'XIIII'),
    (991, 1049, 'XV'),  # 15
    (1050, 1124, 'XVI'),
    (1125, 1191, 'XVII'),
    (1192, 1250, 'XVIII'),
    (1251, 1320, 'XVIIII'),
    (1321, 1382, 'XX'),  # 20
    (1383, 1472, 'XXI'),
    (1473, 1556, 'XXII'),  # 22 -- there is no 24
    (1557, 1650, 'XXIII'),
    (0, 0, 'XXIIII'),  # 24 is not real, but having it in the array makes calcs easier
    (1651, 1739, 'XXV'),
    (1740, 1816, 'XXVI'),  # 26
    (1817, 1887, 'XXVII'),
    (1888, 1962, 'XXVIII'),
    (1963, 2038, 'XXVIIII'),
    (2039, 2143, 'XXX'),  # 30
    (2144, 2220, 'XXXI'),
    (2221, 2311, 'XXXII'),
    (2312, 2390, 'XXXIII'),
    (2391, 2459, 'XXXIIII'),
    (2460, 2601, 'XXXV'),  # 35
    (2602, 2693, 'XXXVI'),
    (2694, 2751, 'XXXVII'),
    (2752, 2820, 'XXXVIII'),
    (2821, 2891, 'XXXVIIII'),
    (2892, 2945, 'XL'),  # 40
    (2946, 3057, 'XLI'),
    (3058, 3136, 'XLII'),
    (3137, 3182, 'XLIII')
]



# Commented out code for reference - this was used to generate the LINE_NUMBER_MARKERS
# number_markers = {}
# offset = 0
# for i in range(0, 3182):
#     if i == 386:
#         offset += 1
#     if i == 1167:
#         offset += 2
#     if i == 1704:
#         offset -= 1
#     if i == 2228:
#         offset -= 2
#     if i == 2231:
#         offset -= 1
#     if i == 2996:
#         offset = -2
#     if i > 0 and i % 5 == 0:
#         number_markers[i + offset] = i + offset
#
# print(number_markers)
