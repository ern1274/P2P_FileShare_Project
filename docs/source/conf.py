# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys
sys.path.insert(0, os.path.abspath('../../'))


project = 'Peer-to-Peer File Sharing'
copyright = '2025, Joshua Talbot and Ethan Nunez'
author = 'Joshua Talbot and Ethan Nunez'
release = '1.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon'
]

templates_path = ['_templates']
exclude_patterns = []

latex_elements = {
    'papersize': 'letterpaper',
    'pointsize': '10pt',
    'classoptions': ',oneside',
    'extraclassoptions': 'openany',  # Allows chapters to start on any page (not just odd)
    'babel': '\\usepackage[english]{babel}',
    'preamble': r'''
        \usepackage{titlesec}
        \titlespacing*{\chapter}{0pt}{-30pt}{20pt}
        \titlespacing*{\section}{0pt}{-10pt}{10pt}
        \usepackage{etoolbox}
        \patchcmd{\chapter}{\thispagestyle{plain}}{}{}{}
    ''',
    'figure_align': 'H',
}


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'alabaster'
html_static_path = ['_static']
