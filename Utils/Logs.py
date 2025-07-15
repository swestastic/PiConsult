import os
import datetime

def Create_Log_File(Log_Index):
    # Creates a log file based on the Log index
    log_filename = f"log_{Log_Index}.txt"
    log_path = os.path.join('Logs', log_filename)
    
    if not os.path.exists('Logs'):
        os.makedirs('Logs')
    
    if not os.path.exists(log_path): # check if the log file already exists
        # If it doesn't exist, create it and write the initial log entry

        with open(log_path, 'w') as log_file:
            log_file.write(f'Log file created on {datetime.datetime.now()}\n')
            log_file.write('Log Index: {Log_Index}\n')

    else:
        # if it exists, append to the existing file
        print("Log file already exists. Appending to the existing file.")
        with open(log_path, 'w') as log_file:
            log_file.write(f'Log file already exists, appending {datetime.datetime.now()}\n')
            log_file.write('Log Index: {Log_Index}\n')

    return log_path

def WriteLog(Log_Index, exception, occurance):
    # Write data to the log file. Takes an exception and the occurance.
    # Ex. "Exception: OSEsrror, Occurance: Trying to connect to serial port"
    log_filename = f"log_{Log_Index}.txt"
    log_path = os.path.join('Logs', log_filename)
    with open(log_path, 'w') as log_file:
        log_file.write(f'Exception: {exception}\n')
        log_file.write(f'Occurance: {occurance}\n')
        log_file.write('\n')
