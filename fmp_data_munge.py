import os,sys
import argparse
import csv
import pandas as pd
import logging
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
LGLVL = os.environ['LOGLEVEL']

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
    )
log = logging.getLogger( __name__ )
log.info( f'\n\n`log` logging working, using level, ``{LGLVL}``' )

ch = logging.StreamHandler()    # ch stands for `Console Handler`
ch.setLevel(logging.WARN)       # note: this level is _not_ the same as the file-handler level set in the `.env`
ch.setFormatter( logging.Formatter(
    '[%(asctime)s] %(levelname)s [%(module)s-%(funcName)s()::%(lineno)d] %(message)s',
    datefmt='%d/%b/%Y %H:%M:%S',
    )
)
log.addHandler(ch)


def read_csv(file_path: str) -> list[list[str]]:
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
    
def make_df(data: list[list[str]]) -> pd.DataFrame:
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

def create_lc_name(**fields) -> str:
    """
    Create a Library of Congress name from the name, date, role, and URI
    
    Args:
        name (str): The name of the person
        date (str): The date of the person
        role (str): The role of the person
        uri (str): The URI of the person
        
    Returns:
        str: The Library of Congress name
    """
    log.debug(f'entering create_lc_name, ``{fields = }``')
    name = fields.get('name', None)
    date = fields.get('date', None)
    role = fields.get('role', None)
    uri = fields.get('uri', None)
    
    role_uri_merge = ' '.join([ i for i in [role, uri] if i])
    return ', '.join([i for i in [name, date, role_uri_merge] if i])


def create_lc_from_piped_fields(func, **kwargs) -> str | None:
    """
    Create a Library of Congress field from piped fields

    Args:
        func: The function to apply to the piped fields
        *args: The piped fields to process

    Returns:
        str: The Library of Congress field
    """

    log.debug(f'entering create_lc_from_piped_fields, ``{func = }, {kwargs = }``')
    split_fields = {k: v.split('|') for k, v in kwargs.items() if v is not None}
    
    log.debug(f'split_fields, ``{split_fields}``')
    
    lc_values = []
    for values in zip(*split_fields.values()):
        log.debug(f'values, ``{values}``')
        lc_values.append(func(**dict(zip(split_fields.keys(), values))))
    
    log.debug(f'lc_values, ``{lc_values}``')
    if not lc_values:
        log.debug(f'No LC values created, returning None')
        return None
    if not lc_values[0]:
        log.debug(f'LC value is empty string or ``[None]``, returning None')
        return None
    log.debug(f'Concatenating LC values {lc_values = }')
    concatenated_lc_values = '|'.join([i if i else '' for i in lc_values])
    print(concatenated_lc_values)
    return concatenated_lc_values

def create_lc_date(start_date: str | None, end_date: str | None) -> str | None:
    """
    Create a Library of Congress date from the start and end dates

    Args:
        start_date (str): The start date
        end_date (str): The end date
    
    Returns:
        str: The Library of Congress date
    """

    return ' - '.join([i for i in [start_date, end_date] if i])
    
def build_uri(authority: str | None, id: str | None) -> str | None:
    """
    Build a URI from an authority and an ID. The authority can be 'lc' or 'viaf'.

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

# def validate_uri(uri: str, authority: str) -> bool:
#     auth_dict = {
#         'lc': 'http://id.loc.gov/authorities/',
#         'viaf': 'http://viaf.org/viaf/'
#     }

#     if uri.startswith(auth_dict[authority.lower()]):
#         return True
#     else:
#         return False
    
# def return_valid_uri(uri: str, authority: str) -> str:
#     if validate_uri(uri, authority):
#         return uri
#     else:
#         raise ValueError(f'Invalid URI: {uri}')

def process_row(row: pd.Series, 
                name_col: str, 
                role_col: str, 
                authority_col: str, 
                authority_id_col: str, 
                new_column_name: str,
                start_date_col: str | None = None, 
                end_date_col: str | None = None
                ) -> pd.Series:
    """
    Process a row of a DataFrame to create a new column with a Library of Congress name
    
    Args:
        row (pd.Series): The row to process
        name_col (str): The name of the column containing the name
        role_col (str): The name of the column containing the role
        authority_col (str): The name of the column containing the authority
        authority_id_col (str): The name of the column containing the authority ID
        new_column_name (str): The name of the new column to create
        start_date_col (str): The name of the column containing the start date
            start and end date columns are optional, but if one is provided, 
            both must be provided
        end_date_col (str): The name of the column containing the end date
        
    Returns:
        pd.Series: The processed row
    """

    if start_date_col and end_date_col:
        lc_date = create_lc_from_piped_fields(create_lc_date, start_date=row[start_date_col], end_date=row[end_date_col])
        log.debug(f'Created LC date with create_lc_from_piped_fields: {lc_date}')
    else:
        lc_date = None
        log.debug(f'No LC date created, start_date_col and/or end_date_col not provided: {start_date_col = }, {end_date_col = }')
    valid_uri = create_lc_from_piped_fields(build_uri, authority=row[authority_col], id=row[authority_id_col])
    log.debug(f'Created valid URI with create_lc_from_piped_fields: {valid_uri}')
    row[new_column_name] = create_lc_from_piped_fields(create_lc_name, name=row[name_col], date=lc_date, role=row[role_col], uri=valid_uri)
    log.debug(f'Created LC name with create_lc_from_piped_fields: {row[new_column_name]}')
    log.debug(f'Processed row: {row}')
    log.debug(f'Exiting process_row')
    return row


def add_lc_name_column(df: pd.DataFrame, 
                       name_col: str, 
                       role_col: str, 
                       authority_col: str, 
                       authority_id_col: str, 
                       new_column_name: str
                       ) -> pd.DataFrame:
    """
    Add a new column to a DataFrame with a Library of Congress name

    Args:
        df (pd.DataFrame): The DataFrame to process
        name_col (str): The name of the column containing the name
        role_col (str): The name of the column containing the role
        authority_col (str): The name of the column containing the authority
        authority_id_col (str): The name of the column containing the authority ID
        new_column_name (str): The name of the new column to create

    Returns:
        pd.DataFrame: The DataFrame with the new column added
    """
    log.debug(f'entering add_lc_name_column')
    new_df = df.apply(process_row, args=(name_col, role_col, authority_col, authority_id_col, new_column_name), axis=1)
    return new_df
    
        


def main():
    # Process command line arguments using argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('file_path', help='Path to the CSV file to be read')
    args = parser.parse_args()
    log.info(f'successfully parsed args, ``{args}``')

    # Read the CSV file
    data = read_csv(args.file_path)
    df = make_df(data)


    # # Create some test data
    # names = 'Smith, John|Jones, Mary|Brown, David'
    # dates = '1970|1980|1990'
    # roles = 'author|illustrator|editor'
    # uris = 'http://id.loc.gov/authorities/names/n79021383|http://id.loc.gov/authorities/names/n79021384|http://id.loc.gov/authorities/names/n79021385'
    # create_lc_name_from_piped_fields(names, dates, roles, uris)
    new_df = add_lc_name_column(df, name_col='Authoritized Name', authority_id_col='Authority ID', authority_col='Authority Used', role_col='Position', new_column_name='namePersonOtherVIAF')
    print(new_df.head())
    log.info(f'Finished processing DataFrame, writing to CSV')
    if not os.path.exists('../output'):
        os.makedirs('../output')
    new_df.to_csv('../output/processed_data.csv', index=False)

if __name__ == '__main__':
    main()