import boto3  
import os, logging  
import datetime


# Set the global variables
globalVars  = {}
globalVars['Owner']                 = "Miztiik"
globalVars['Environment']           = "Development"
globalVars['REGION_NAME']           = "eu-central-1"
globalVars['tagName']               = "Serverless-Automated-Backup"
globalVars['findNeedle']            = "BackUp"
globalVars['RetentionTag']          = "DeleteOn"
globalVars['RetentionInDays']       = "30"

# Customize to your region as needed
# ec = boto3.client('ec2', region_name='ap-south-1')
ec = boto3.client('ec2')
logger = logging.getLogger()

"""
If User provides different values, override defaults
"""
def setGlobalVars():
    try:
        if os.environ['RetentionTag']:
            globalVars['RetentionTag']  = os.environ['RetentionTag']
        if os.environ['RetentionDays']:
            globalVars['RetentionDays'] = os.environ['RetentionDays']
    except KeyError as e:
        logger.error("User Customization Environment variables are not set")
        logger.error('ERROR: {0}'.format( str(e) ) )

def backup_bot():

    snapsCreated = { 'Snapshots':[], 'FailedSnaps':[] }
    snapsToTag = []

    # Filter for instances having the needle tag
    FILTER_1 = [
        {'Name': 'tag:' + globalVars['findNeedle'],  'Values': ['Yes', 'yes', 'YES']}
        ]

    reservations = ec.describe_instances( Filters = FILTER_1 ).get( 'Reservations', [] )

    instances = sum(
        [
            [i for i in r['Instances']]
            for r in reservations
        ], [])

    # print "Number of the Instances : %d" % len(instances)
    snapsCreated['InstanceCount']=len(instances)

    # Iterate for all Instances in the Region
    for instance in instances:
        try:
            retention_days = [
                int(t.get('Value')) for t in instance['Tags']
                if t['Key'] == 'Retention'][0]
        except IndexError:
            retention_days = int(globalVars['RetentionInDays'])

        # Get all the Block Device Mappings
        for dev in instance['BlockDeviceMappings']:
            if dev.get('Ebs', None) is None:
                continue
            vol_id = dev['Ebs']['VolumeId']

            # Iterate Tags to collect the instance name tag
            DescriptionTxt = ''
            for tag in instance['Tags']:
                if tag['Key'] == 'Name' :
                    DescriptionTxt = tag['Value']
            try:
                snap = ec.create_snapshot( VolumeId=vol_id, Description=DescriptionTxt )
                
                # to mention the current date formet
                delete_date = datetime.date.today() + datetime.timedelta( days = retention_days )
                # below code is create the name and current date as instance name
                delete_fmt = delete_date.strftime('%Y-%m-%d')
                
                # Add the Deletion Tag to tag list
                instance['Tags'].append( { 'Key': globalVars['RetentionTag'], 'Value': delete_fmt } )
                snapsCreated['Snapshots'].append( {'SnapshotID':snap['SnapshotId'],
                                                   'VolumeId' : vol_id,
                                                   'InstanceId' : instance['InstanceId'],
                                                   'Tags':instance['Tags'],
                                                   'RetentionDays':retention_days,
                                                   globalVars['RetentionTag']:delete_fmt 
                                                   }
                                                 )
            except Exception as e:
                snapsCreated['FailedSnaps'].append( {'VolumeId':vol_id, 'ERROR':str(e), 'Message':'Unable to trigger snapshot'})
                pass


        # Tag all the snaps that were created today with Deletion Date
        # Processing "DeleteOn" here to allow for future case of each disk having its own Retention date
        for snap in snapsCreated['Snapshots']:
            ec.create_tags(
                            Resources=[ snap['SnapshotID'] ],
                            Tags = snap['Tags']
                        )
    return snapsCreated


def lambda_handler(event, context):
    setGlobalVars()
    return backup_bot()

if __name__ == '__main__':
    lambda_handler(None, None)