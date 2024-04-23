#region IMPORTS
import os, sys
import argparse
import csv
import logging
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass
import requests
import time


import pandas as pd
from dotenv import load_dotenv, find_dotenv
#endregion

load_dotenv(find_dotenv())
LGLVL = os.environ['LOGLEVEL']

#region LOGGING
## set up logging ---------------------------------------------------
lglvldct = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARN': logging.WARNING
}
logging.basicConfig(
    level=lglvldct[LGLVL],  # type: ignore -- assigns the level-object to the level-key loaded from the envar
    format='[%(asctime)s] %(levelname)s [%(module)s-%(funcName)s()::%(lineno)d] %(message)s',
    datefmt='%d/%b/%Y %H:%M:%S',
    # encoding='utf-8',
    filename='../fmp_data_munge.log',
    filemode='w'  # Set filemode to 'w' to overwrite the existing log file
)
log = logging.getLogger(__name__)
log.info(f'\n\n`log` logging working, using level, ``{LGLVL}``')

ch = logging.StreamHandler()  # ch stands for `Console Handler`
ch.setLevel(logging.WARN)  # note: this level is _not_ the same as the file-handler level set in the `.env`
ch.setFormatter(logging.Formatter(
    '[%(asctime)s] %(levelname)s [%(module)s-%(funcName)s()::%(lineno)d] %(message)s',
    datefmt='%d/%b/%Y %H:%M:%S',
))
log.addHandler(ch)
#endregion

#region CLASSES

# region
# # Create a namedtuple Class to store the formatted output chunks
# class FormattedOutput(NamedTuple):
#     """
#     A named tuple 'FormattedOutput' is used to specify how to create a new column in the process_row function.

#     Attributes:
#         text (str): The static text to include in the new column. Default is None.
#         column_name (str): The name of an existing column whose values are to be included in the new column. Default is None.
#         function (function): A function that returns a string to be included in the new column. Default is None.
#         kwargs (dict): The keyword arguments to pass to the function. Default is None.

#     Any given attribute can be None, but if using a function, the kwargs must be provided.

#     Examples:
#         FormattedOutput can be used in the following ways:

#         ```
#         FormattedOutput(text=',', column_name=None, function=None, kwargs=None)
#         FormattedOutput(text=None, column_name='Authoritized Name', function=None, kwargs=None)
#         FormattedOutput(text=None, column_name=None, function=create_formatted_date, kwargs={'start_date': 'Start Date', 'end_date': 'End Date'})
#         ```
#     """
#     text: str | None
#     column_name: str | None
#     function: Callable | None
#     kwargs: dict[str, str] | None
# endregion

@dataclass
class FormattedOutput:
    """
    A dataclass 'FormattedOutput' is used to specify how to create a new column in the process_row function.

    Attributes:
        text (str): The static text to include in the new column. Default is None.
        column_name (str): The name of an existing column whose values are to be included in the new column. Default is None.
        function (Callable): A function that returns a string to be included in the new column. Default is None.
        kwargs (Dict[str, str]): The keyword arguments to pass to the function. Default is None.

    Any given attribute can be None, but if using a function, the kwargs must be provided.

    Examples:
        FormattedOutput can be used in the following ways:

        ```
        FormattedOutput(text=',', column_name=None, function=None, kwargs=None)
        FormattedOutput(text=None, column_name='Authoritized Name', function=None, kwargs=None)
        FormattedOutput(text=None, column_name=None, function=create_formatted_date, kwargs={'start_date': 'Start Date', 'end_date': 'End Date'})
        ```
    """
    text: Optional[str] = None
    column_name: Optional[str] = None
    function: Optional[Callable] = None
    kwargs: Optional[Dict[str, str]] = None
#endregion

#region FUNCTIONS
# =============================================================================
# FUNCTIONS
# =============================================================================


def read_csv(file_path: str) -> list[list[str]]: # MARK: read_csv
    """
    Read a CSV file and return the data as a list of lists

    Args:
        file_path (str): The path to the CSV file

    Returns:
        list[list[str]]: The data from the CSV file
    """

    with open(file_path, 'r') as f:
        reader = csv.reader(f)
        data = [row for row in reader]
        log.info(f'Read {len(data)} rows from {file_path}')
        return data
    
def make_df(data: list[list[str]]) -> pd.DataFrame: # MARK: make_df
    """
    Create a pandas DataFrame from a list of lists
    
    Args:
        data (list[list[str]]): The data to be converted to a DataFrame,
            in the format created by the read_csv function
        
    Returns:
        pd.DataFrame: The pandas DataFrame
    """

    df = pd.DataFrame(data[1:], columns=data[0])
    print(df.info())
    log.info(f'Created DataFrame with {len(df)} rows and {len(df.columns)} columns')
    return df

def create_authority_name(**fields) -> str: # MARK: create_authority_name
    """
    Create an 'authority' name from the name, date, role, and URI

    Example:
        input: 'Smith, John', '1970', 'author', 'http://id.loc.gov/authorities/names/n79021383'
        output: 'Smith, John, 1970, author http://id.loc.gov/authorities/names/n79021383'
    
    Args:
        name (str): The name of the person
        date (str): The date of the person
        role (str): The role of the person
        uri (str): The URI of the person
        
    Returns:
        str: The formatted name
    """
    log.debug(f'entering create_authority_name, ``{fields = }``')
    name = fields.get('name', None)
    date = fields.get('date', None)
    role = fields.get('role', None)
    uri = fields.get('uri', None)
    
    role_uri_merge = ' '.join([ i for i in [role, uri] if i])
    return ', '.join([i for i in [name, date, role_uri_merge] if i])

def create_formatted_date(start_date: str | None, end_date: str | None) -> str | None: # MARK: create_formatted_date
    """
    Create a date range in 'YYYY - YYYY' format from a start date and an end date,
    or a single date if only one is provided

    Args:
        start_date (str): The start date
        end_date (str): The end date
    
    Returns:
        str: The formatted date (range)
    """

    return ' - '.join([i for i in [start_date, end_date] if i])
    
def build_uri(authority: str | None, id: str | None) -> str | None: # MARK: build_uri
    """
    Build a URI from an authority and an ID. The authority can be 'lc', 'viaf', or local. If local, returns None.

    Args:
        authority (str): The authority
        id (str): The ID

    Returns:
        str: The URI
    """

    auth_dict = {
        'lc': 'http://id.loc.gov/authorities/names/',
        'viaf': 'http://viaf.org/viaf/'
    }

    if not authority:
        log.debug(f'No authority provided: {authority = }, {id = }')
        return None
    if authority.lower() == 'local':
        log.debug(f'Local authority provided: {authority = }, {id = }')
        return None
    uri = f'{auth_dict[authority.lower()]}{id}'
    log.debug(f'Created URI: {uri}')

    return uri

def reduce_list(values: str, flags: list[bool]) -> str: # MARK: reduce_list
    """
    Reduce a list of values based on a list of boolean flags

    Example:
        input: 'a|b|c', [True, False, True]
        output: 'a|c'
    
    Args:
        values str: The pipe-separated list of values
        flags (list[bool]): The flags to reduce by
        
    Returns:
        str: The reduced list of values
    """

    return '|'.join([value for value, flag in zip(values.split('|'), flags) if flag])

def process_row(row: pd.Series,
                new_column_name: str, 
                output_format: list[FormattedOutput],
                mask_column: str | None = None,
                mask_value: str | None = None
                ) -> pd.Series: # MARK: process_row

    """
    Process a row of a DataFrame to create a new column with a format specified by the FormattedOutput namedtuple

    Args:
        row (pd.Series): The row to process
        output_format (list[FormattedOutput]): A list of FormattedOutput namedtuples specifying how to create the new column
        mask_column (str): The name of the column to use as a mask
        mask_value (str): The value to use as a mask filter, only values in mask_column matching this value will be processed (case-insensitive)

    Any given attribute can be None, but if using a function, the kwargs must be provided.
    If multiple attributes are provided, they will be concatenated in the order they are provided.

    Returns:
        pd.Series: The processed row

    Example:
        This is a partial example of output_format for the name and date range:
        ```
        output_format = [
            FormattedOutput(text=None, column_name='Authoritized Name', function=None, kwargs=None),
            FormattedOutput(text=', ', column_name=None, function=None, kwargs=None),
            FormattedOutput(text=None, column_name=None, function=create_formatted_date, kwargs={'start_date': 'Start Date', 'end_date': 'End Date'})
        ]
        ```

        This is an example of using the mask_column and mask_value arguments:
        ```
        new_df = df.apply(process_row, args=(output_format, 'Authority Used', 'viaf'), axis=1)
        ```
    """

    log.debug(f'entering process_row')

    # check that mask_column and mask_value are both provided or both None
    if isinstance(mask_column, str) ^ isinstance(mask_value, str):
        raise ValueError('Both mask_column and mask_value must be provided')
    
    # track the indices to process based on the mask
    if mask_column and mask_value:
        log.debug(f'{mask_column = }, {mask_value = }')
        values_to_process = [True if i.lower() == mask_value.lower() else False for i in row[mask_column].split('|')]
        log.debug(f'{values_to_process = }')
    else:
        values_to_process = [True] * len(row)
        log.debug(f'No mask provided, processing all values: {values_to_process = }')

    formatted_output_values: list[str] = []

    for i, value in enumerate(values_to_process):
        if value:
            formatted_text: str = ''
            for chunk in output_format:
                # check that function and kwargs are both provided or both None
                if callable(chunk.function) ^ isinstance(chunk.kwargs, dict):
                    raise ValueError("FormattedOutput must specify both 'function' and 'kwargs' or neither")
                if chunk.text:
                    formatted_text += chunk.text
                if chunk.column_name:
                    formatted_text += row[chunk.column_name].split('|')[i]
                if chunk.function:
                    built_kwargs: dict = {}
                    for k, v in chunk.kwargs.items(): # type: ignore
                        built_kwargs[k] = row[v].split('|')[i]
                    formatted_text += chunk.function(**built_kwargs)
            formatted_output_values.append(formatted_text)

    row[new_column_name] = '|'.join(formatted_output_values)
    log.debug(f'Processed row: {row}')
    return row

def add_nameCorpCreatorLocal_column(row: pd.Series) -> pd.Series: # MARK: add_nameCorpCreatorLocal_column
    """
    Process a row of a DataFrame to create a new column, 
    populating it with the 'Organization Name' from the 'sources' sheet if neither 'LCNAF' nor 'VIAF' names are found.

    Args:
        row (pd.Series): The row to process

    Returns:
        pd.Series: The processed row
    """

    log.debug(f'entering add_nameCorpCreatorLocal_column')

    # check if 'nameCorpCreatorLC' is empty
    if row['nameCorpCreatorLC']:
        log.debug(f'nameCorpCreatorLC is not empty, returning row')
        row['nameCorpCreatorLocal'] = ''
        return row
    
    # check if 'nameCorpCreatorVIAF' is empty
    if row['nameCorpCreatorVIAF']:
        log.debug(f'nameCorpCreatorVIAF is not empty, returning row')
        row['nameCorpCreatorLocal'] = ''
        return row
    
    # Try to pull the first value from 'Organization Name_sources'
    try:
        row['nameCorpCreatorLocal'] = row['Organization Name_sources'].split('|')[0]
    except IndexError:
        log.debug(f'No Organization Name found in Organization Name_sources, attempting to pull from Organization Name_subjects')
        try:
            row['nameCorpCreatorLocal'] = row['Organization Name_subjects'].split('|')[0]
        except IndexError:
            log.debug(f'No Organization Name found in Organization Name_subjects, setting nameCorpCreatorLocal to empty string')
            row['nameCorpCreatorLocal'] = ''

    log.debug(f'Processed row: {row}')
    return row

def lc_get_subject_uri(subject_term: str) -> str | None: # MARK: lc_api_call
    """
    Call the Library of Congress API to get the URI for a subject term

    Args:
        subject_term (str): The subject term to search for

    Returns:
        str: The URI of the subject term or None if not found
    """

    response = requests.head(f'https://id.loc.gov/authorities/subjects/label/{subject_term}', allow_redirects=True)
    if response.ok:
        url = response.url
        if url.endswith('.json'):
            return url[:-5]
        return url
    return None

def lc_get_name_type(uri: str) -> str | None: # MARK: lc_get_name_type
    """
    Call the Library of Congress API to get the type of a name (Personal or Corporate)

    Args:
        uri (str): The URI to search for

    Returns:
        str: The type of the name or None if not found
    """
    log.debug(f'entering lc_get_name_type')

    response = requests.get(f'{uri}.json')
    if response.ok:
        log.debug(f'LC API call successful')
        data: list[dict[str, Any]] = response.json()
        # find the dictionary with a key of '@id' and a value of the uri
        matching_dict: dict[str, Any] = [d for d in data if d.get('@id', None) == uri][0]
        log.debug(f'{matching_dict = }')
        # get the values from the '@type' key
        name_types: list[str] = matching_dict.get('@type', None)
        log.debug(f'{name_types = }')
        if not name_types:
            return None
        if "http://www.loc.gov/mads/rdf/v1#CorporateName" in name_types:
            return 'Corporate'
        elif "http://www.loc.gov/mads/rdf/v1#PersonalName" in name_types:
            return 'Personal'
        
    return None


def get_unique_values_from_column(column: pd.Series) -> set[str]: # MARK: get_unique_values_from_column
    """
    Get unique values from a column of a DataFrame, separating pipe-separated values

    Args:
        column (pd.Series): The column to process

    Returns:
        set[str]: The unique values
    """
    
    unique_values: set[str] = set()
    for value in column:
        unique_values.update(value.split('|'))
    return unique_values

def build_uri_dict(values: set[str], api_call: Callable) -> dict[str, str]: # MARK: build_uri_dict
    """
    Build a dictionary of URIs from a set of values using an API call

    Args:
        values (set[str]): The values to search for
        api_call (Callable): The function to call to get the URI for a value

    Returns:
        dict[str, str]: The dictionary of values and URIs
    """
    
    uri_dict: dict[str, str] = {}
    for value in values:
        uri = api_call(value)
        if uri:
            uri_dict[value] = uri
        time.sleep(0.2)
    return uri_dict

def add_subjectTopics(row: pd.Series, uri_dict: dict[str, str]) -> pd.Series: # MARK: add_subjectTopics
    """
    Process a row of a DataFrame to populate either subjectTopicsLC or subjectTopicsLocal columns. 
    Populates subjectTopicsLC if an LC URI is found, subjectTopicsLocal if not.

    Args:
        row (pd.Series): The row to process

    Returns:
        pd.Series: The processed row
    """

    log.debug(f'entering add_subjectTopics')

    # Create list of subject terms from pipe-separated values in 'Subject Heading'
    subject_terms: list[str] = row['Subject Heading'].split('|')

    # Iterate through subject terms to find URIs
    uri_terms: list[str] = []
    local_terms: list[str] = []
    for term in subject_terms:
        uri = uri_dict.get(term, None)
        if uri:
            uri_terms.append(f'{term} {uri}')
        else:
            local_terms.append(term)
    if not uri_terms:
        uri_terms = ['']
    if not local_terms:
        local_terms = ['']

    # Concatenate URIs and local terms
    row['subjectTopicsLC'] = '|'.join(uri_terms)
    row['subjectTopicsLocal'] = '|'.join(local_terms)

    log.debug(f'Processed row: {row}')
    return row

def make_name_type_column(row: pd.Series, uri_column: str, authority_column: str) -> pd.Series: # MARK: make_name_type_column
    """
    Process a row of a DataFrame to create a new column,
    populating it with either 'Personal' or 'Corporate' based on an LC API call.

    Args:
        row (pd.Series): The row to process

    Returns:
        pd.Series: The processed row
    """

    log.debug(f'entering make_name_type_column')

    # Get authority and URI values
    authorities: list[str] = row[authority_column].split('|')
    if 'LCNAF' not in authorities:
        row['Name Type'] = ''
        return row
    uris: list[str] = row[uri_column].split('|')

    # Find first LC URI
    uri: str | None = None
    for i, authority in enumerate(authorities):
        if authority == 'LCNAF':
            uri = uris[i]
            break

    # Get name type
    if not uri:
        row['Name Type'] = ''
        return row
    name_type: str | None = lc_get_name_type(uri)
    if not name_type:
        name_type = ''
    row['Name Type'] = name_type

    log.debug(f'Processed row: {row}')
    return row

def handle_person_and_corp_lc_names(row: pd.Series) -> pd.Series: # MARK: handle_person_and_corp_lc_names
    """
    Creates the namePersonCreatorLC and nameCorpCreatorLC columns by handing off to process_row based on the value
    in the 'Name Type' column.

    Args:
        row (pd.Series): The row to process

    Returns:
        pd.Series: The processed row
    """
    
    log.debug(f'entering handle_person_and_corp_lc_names')

    # Check if 'Name Type' is empty
    if not row['Name Type']:
        row['namePersonCreatorLC'] = ''
        row['nameCorpCreatorLC'] = ''
        return row

    output_format: list[FormattedOutput] = [
        FormattedOutput(text=None, column_name='Organization Name_sources', function=None, kwargs=None),
        FormattedOutput(text=' ', column_name=None, function=None, kwargs=None),
        FormattedOutput(text=None, column_name='URI', function=None, kwargs=None)
    ]

    # Check if 'Name Type' is 'Personal'
    if row['Name Type'] == 'Personal':
        row = process_row(row, 'namePersonCreatorLC', output_format, 'Source', 'LCNAF')
        row['nameCorpCreatorLC'] = ''
        return row

    # Check if 'Name Type' is 'Corporate'
    if row['Name Type'] == 'Corporate':
        row = process_row(row, 'nameCorpCreatorLC', output_format, 'Source', 'LCNAF')
        row['namePersonCreatorLC'] = ''
        return row

    log.debug(f'Processed row: {row}')
    return row

#endregion    
        

#region MAIN FUNCTION
def main():
    # Process command line arguments using argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('file_path', help='Path to the CSV file to be read')
    args = parser.parse_args()
    log.info(f'successfully parsed args, ``{args}``')

    # Read the CSV file
    data:list[list[str]] = read_csv(args.file_path)
    df: pd.DataFrame = make_df(data)

    
    # Add the namePersonOtherVIAF column
    output_format: list[FormattedOutput] = [
        FormattedOutput(text=None, column_name='Authoritized Name', function=None, kwargs=None),
        FormattedOutput(text=', ', column_name=None, function=None, kwargs=None),
        FormattedOutput(text=None, column_name='Position', function=None, kwargs=None),
        FormattedOutput(text=' ', column_name=None, function=None, kwargs=None),
        FormattedOutput(text=None, column_name=None, function=build_uri, kwargs={'authority': 'Authority Used', 'id': 'Authority ID'})
    ]
    new_df = df.apply(process_row, args=('namePersonOtherVIAF', output_format, 'Authority Used', 'viaf'), axis=1)

    # # Add the namePersonOtherLocal column
    output_format: list[FormattedOutput] = [
        FormattedOutput(text=None, column_name='Authoritized Name', function=None, kwargs=None),
        FormattedOutput(text=', ', column_name=None, function=None, kwargs=None),
        FormattedOutput(text=None, column_name='Position', function=None, kwargs=None),
    ]
    new_df = new_df.apply(process_row, args=('namePersonOtherLocal', output_format, 'Authority Used', 'local'), axis=1)


    # Make the nameType column
    new_df = new_df.apply(make_name_type_column, args=('URI', 'Source'), axis=1)

    # Add the namePersonCreatorLC and nameCorpCreatorLC columns
    new_df = new_df.apply(handle_person_and_corp_lc_names, axis=1)

    # Add the nameCorpCreatorVIAF column
    output_format: list[FormattedOutput] = [
        FormattedOutput(text=None, column_name='Organization Name_sources', function=None, kwargs=None),
        FormattedOutput(text=' ', column_name=None, function=None, kwargs=None),
        FormattedOutput(text=None, column_name='URI', function=None, kwargs=None)
    ]
    new_df = new_df.apply(process_row, args=('nameCorpCreatorVIAF', output_format, 'Source', 'VIAF'), axis=1)

    # We only want to keep the nameCorpCreatorVIAF column if the nameCorpCreatorLC column is empty
    new_df['nameCorpCreatorVIAF'] = new_df.apply(lambda row: row['nameCorpCreatorVIAF'] if not row['nameCorpCreatorLC'] else '', axis=1)

    # Add the nameCorpCreatorLocal column
#   *nameCorpCreatorLocal (FileMakerPro: sources sheet -> Organization Name, Source)
#       If no LCNAF and no VIAF, find name, pull just one
#       If no name is found as Local, add the Organization Name from the subjects sheet (this will be the same value as in the subjectCorpLocal field)
#       Ex: The Presbyterian Journal

    new_df = new_df.apply(add_nameCorpCreatorLocal_column, axis=1)

    # Add the subjectTopicsLC and subjectTopicsLocal columns
    unique_subjects = get_unique_values_from_column(new_df['Subject Heading'])
    uri_dict = build_uri_dict(unique_subjects, lc_get_subject_uri)
    new_df = new_df.apply(add_subjectTopics, args=(uri_dict,), axis=1)


    # Grab some values from the newly created column to print for testing
    check_vals: list[str] = new_df['subjectTopicsLC'].tolist()
    print(check_vals[:10])

    check_vals: list[str] = new_df['subjectTopicsLocal'].tolist()
    print(check_vals[:10])


    print(new_df.head())
    log.info(f'Finished processing DataFrame, writing to CSV')
    if not os.path.exists('../output'):
        os.makedirs('../output')
    new_df.to_csv('../output/processed_data.csv', index=False)

#endregion

#region DUNDER MAIN
if __name__ == '__main__':
    main()
#endregion