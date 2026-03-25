import pandas as pd

# Load the tables
exp_table0 = pd.read_csv('exp0_table0.csv')
exp_table1 = pd.read_csv('exp0_table1.csv')
exp_table2 = pd.read_csv('exp0_table2.csv')
exp_table3 = pd.read_csv('exp0_table3.csv')

# Remove the first three columns from tables 1, 2, 3
exp_table1 = exp_table1.iloc[:, 3:]
exp_table2 = exp_table2.iloc[:, 3:]
exp_table3 = exp_table3.iloc[:, 3:]

# Join the tables column by column
joined_table = pd.concat([exp_table0, exp_table1, exp_table2, exp_table3], axis=1)
# Save the joined table to a new CSV file
# joined_table.to_csv('joined_table.csv', index=False)
# Add a numbering column as the first column starting from 1
joined_table.insert(0, '', range(1, len(joined_table) + 1))

# Save the joined table to a new CSV file
joined_table.to_csv('exp0.csv', index=False)
