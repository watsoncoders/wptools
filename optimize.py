import os
import re
import requests
from bs4 import BeautifulSoup
import mysql.connector

# MySQL Database Connection (Replace with your credentials)
def connect_to_db(host, user, password, database):
    try:
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
        return connection
    except mysql.connector.Error as err:
        print(f"Error connecting to the database: {err}")
        return None

# Query the wp_options table for autoloaded options
def check_wp_options_autoloaded(connection):
    issues = []
    try:
        cursor = connection.cursor(dictionary=True)
        # Query for autoloaded options
        cursor.execute("""
            SELECT option_name, option_value, LENGTH(option_value) AS size 
            FROM wp_options 
            WHERE autoload = 'yes' 
            ORDER BY size DESC
            LIMIT 10;
        """)
        results = cursor.fetchall()
        
        if results:
            issues.append("Autoloaded options found that may impact performance. Consider optimizing the following options:")
            for row in results:
                issues.append(f"Option: {row['option_name']} (Size: {row['size']} bytes)")
                # Suggest query to remove autoload for large options
                if row['size'] > 1000:  # Example threshold, you can adjust
                    issues.append(f"SQL Suggestion: `UPDATE wp_options SET autoload = 'no' WHERE option_name = '{row['option_name']}';`")
    except mysql.connector.Error as err:
        issues.append(f"Error querying the wp_options table: {err}")
    
    return issues

# Query to clean up expired transients
def check_expired_transients(connection):
    issues = []
    try:
        cursor = connection.cursor()
        # Query for expired transients
        cursor.execute("""
            DELETE FROM wp_options 
            WHERE option_name LIKE '_transient_%' 
            AND option_value < UNIX_TIMESTAMP();
        """)
        connection.commit()
        issues.append("Expired transients have been removed from the wp_options table.")
    except mysql.connector.Error as err:
        issues.append(f"Error cleaning up expired transients: {err}")
    
    return issues

# Suggest cleaning up post revisions in wp_posts
def check_post_revisions(connection):
    issues = []
    try:
        cursor = connection.cursor(dictionary=True)
        # Query for posts with excessive revisions
        cursor.execute("""
            SELECT COUNT(*) AS revision_count, post_parent 
            FROM wp_posts 
            WHERE post_type = 'revision' 
            GROUP BY post_parent 
            HAVING revision_count > 10;
        """)
        results = cursor.fetchall()
        
        if results:
            issues.append("Found posts with excessive revisions. Consider limiting post revisions.")
            for row in results:
                issues.append(f"Post ID: {row['post_parent']} has {row['revision_count']} revisions.")
            issues.append("SQL Suggestion: `DELETE FROM wp_posts WHERE post_type = 'revision' AND post_parent = X;`")
    except mysql.connector.Error as err:
        issues.append(f"Error querying post revisions: {err}")
    
    return issues

# Remove orphaned postmeta entries
def check_orphaned_postmeta(connection):
    issues = []
    try:
        cursor = connection.cursor()
        # Query for orphaned postmeta
        cursor.execute("""
            DELETE pm
            FROM wp_postmeta pm
            LEFT JOIN wp_posts wp ON wp.ID = pm.post_id
            WHERE wp.ID IS NULL;
        """)
        connection.commit()
        issues.append("Orphaned postmeta entries have been removed.")
    except mysql.connector.Error as err:
        issues.append(f"Error removing orphaned postmeta: {err}")
    
    return issues

# Suggest adding or optimizing indexes
def check_missing_indexes(connection):
    issues = []
    try:
        cursor = connection.cursor(dictionary=True)
        # Example query: Check if there is an index on the postmeta table's post_id
        cursor.execute("""
            SHOW INDEX FROM wp_postmeta WHERE Column_name = 'post_id';
        """)
        results = cursor.fetchall()
        
        if not results:
            issues.append("Index on wp_postmeta.post_id is missing. Consider adding an index for better performance.")
            issues.append("SQL Suggestion: `CREATE INDEX post_id_index ON wp_postmeta (post_id);`")
    except mysql.connector.Error as err:
        issues.append(f"Error checking for missing indexes: {err}")
    
    return issues

# Check for database optimizations
def check_database_optimizations(connection):
    issues = []

    # Check autoloaded options
    issues.extend(check_wp_options_autoloaded(connection))

    # Check for expired transients
    issues.extend(check_expired_transients(connection))

    # Check for excessive post revisions
    issues.extend(check_post_revisions(connection))

    # Check for orphaned postmeta
    issues.extend(check_orphaned_postmeta(connection))

    # Check for missing indexes
    issues.extend(check_missing_indexes(connection))

    return issues

# Main function to run the tool
def run_scan(url, path_to_wp_config, wp_content_path, db_config):
    # Scan the HTML of the site
    html = scan_site(url)
    if html:
        performance_issues = check_performance(html)
        security_issues = check_security(html)
        
        print("\nPerformance Issues Found:")
        for issue in performance_issues:
            print(f"- {issue}")
        
        print("\nSecurity Issues Found:")
        for issue in security_issues:
            print(f"- {issue}")
        
        # Check wp-config.php for hardening suggestions
        wp_config_issues = check_wp_config(path_to_wp_config)

        # Check for unused plugins/themes
        plugin_theme_issues = check_unused_plugins_and_themes(wp_content_path)

        # Connect to the database and check for optimizations
        connection = connect_to_db(db_config['host'], db_config['user'], db_config['password'], db_config['database'])
        if connection:
            db_issues = check_database_optimizations(connection)
            connection.close()
        else:
            db_issues = ["Unable to connect to the database for optimization checks."]
        
        # Provide PHP suggestions for improvements
        php_suggestions = suggest_php_fixes(performance_issues, security_issues, wp_config_issues, plugin_theme_issues, db_issues)

        print("\nPHP Suggestions for Improvements:")
        for suggestion in php_suggestions:
            print(f"- {suggestion}")
    else:
        print("Failed to retrieve site data.")

# Example usage
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'your_password',
    'database': 'wordpress_db'
}

run_scan('https://example.com', '/path/to/wp-config.php', '/path/to/wp-content', db_config)
