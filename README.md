# Benchmark the performance and throughput for [Amazon EBS](https://aws.amazon.com/ebs/), [Amazon EFS](https://aws.amazon.com/efs), [Amazon FSx for Open ZFS](https://aws.amazon.com/fsx/openzfs/), and [Amazon S3 Express One Zone](https://aws.amazon.com/s3/storage-classes/express-one-zone/) with [Mountpoint for Amazon S3](https://aws.amazon.com/s3/features/mountpoint/) when running hundreds of Yocto Linux builds in parallel


## 1 Setup

Following setup was selected:
- AWS region: N. Virginia (us-east-1)
- OS: Ubuntu 22.04 LTS release as base image
- all file systems are encrypted with the default service KMS key, except for the instance root volume (because it doesn't contain sensitive data)

Store a couple environment variables, to make the benchmark a bit easier when running the commands. Replace <REPLACE ME> with the parameters of your environment:

```bash
# the AWS region to be used for the benchmark. I have chosen us-east-1.
AWS_REGION=<REPLACE ME>

# this is the SSH key name we provision the Amazon EC2 instances with, in case you want to SSH into the instance (e.g. to troubleshoot an issue)
SSH_KEY_PAIR_NAME=<REPLACE ME>

# this is the Amazon S3 bucket, where we upload the benchmark results for later analysis
S3_BUCKET_NAME=<REPLACE ME>

# these are the subnets we use to mount the EFS/FSx/S3 file systems
SUBNET_1_ID=<REPLACE ME>
SUBNET_2_ID=<REPLACE ME>
SUBNET_3_ID=<REPLACE ME>
SUBNET_4_ID=<REPLACE ME>
SUBNET_5_ID=<REPLACE ME>
SUBNET_6_ID=<REPLACE ME>

# the security group we use for controlling access to the EFS/FSx file systems
SECURITY_GROUP_ID=<REPLACE ME>
```


## 2 Create the file systems

### 2.1 Create the EFS file systems

> NOTE  
> You only have to go through this section, if you want to run the benchmark using EFS!

We create an Amazon EFS file system with `generalPurpose` performance mode and `elastic` throughput mode and the corresponding mount points in each availability zone. To benchmark other performance and throughput mode configurations, modify these parameters or set-up another file system: 
```bash
aws efs create-file-system \
    --region $AWS_REGION \
    --output json \
    --encrypted \
    --performance-mode generalPurpose \
    --throughput-mode elastic \
    --no-backup \
    --tags Key=Name,Value=Yocto-Poky-Storage-Benchmark-EFS-General-Purpose Key=owner,Value=cmr \
    | jq "."

EFS_FILE_SYSTEM_ID=$(aws efs describe-file-systems \
    --region $AWS_REGION \
    --output json \
    | jq -r '.FileSystems | .[] | select(.Name == "Yocto-Poky-Storage-Benchmark-EFS-General-Purpose") | .FileSystemId')
echo "EFS file system id is: $EFS_FILE_SYSTEM_ID"

aws efs create-mount-target \
    --region $AWS_REGION \
    --output json \
    --file-system-id $EFS_FILE_SYSTEM_ID \
    --subnet-id $SUBNET_1_ID \
    --security-groups $SECURITY_GROUP_ID \
    | jq '.'

aws efs create-mount-target \
    --region $AWS_REGION \
    --output json \
    --file-system-id $EFS_FILE_SYSTEM_ID \
    --subnet-id $SUBNET_2_ID \
    --security-groups $SECURITY_GROUP_ID \
    | jq '.'

aws efs create-mount-target \
    --region $AWS_REGION \
    --output json \
    --file-system-id $EFS_FILE_SYSTEM_ID \
    --subnet-id $SUBNET_3_ID \
    --security-groups $SECURITY_GROUP_ID \
    | jq '.'
    
aws efs create-mount-target \
    --region $AWS_REGION \
    --output json \
    --file-system-id $EFS_FILE_SYSTEM_ID \
    --subnet-id $SUBNET_4_ID \
    --security-groups $SECURITY_GROUP_ID \
    | jq '.'
    
aws efs create-mount-target \
    --region $AWS_REGION \
    --output json \
    --file-system-id $EFS_FILE_SYSTEM_ID \
    --subnet-id $SUBNET_5_ID \
    --security-groups $SECURITY_GROUP_ID \
    | jq '.'
    
aws efs create-mount-target \
    --region $AWS_REGION \
    --output json \
    --file-system-id $EFS_FILE_SYSTEM_ID \
    --subnet-id $SUBNET_6_ID \
    --security-groups $SECURITY_GROUP_ID \
    | jq '.'
```

### 2.2 Create the FSx for Open ZFS file systems

> NOTE  
> You only have to go through this section, if you want to run the benchmark using FSx for Open ZFS!

We create the Amazon FSx for Open ZFS file system with `1024` GB storage capacity, `4096` throughput capacity and provisioned Iops of `20000`.:
```bash
aws fsx create-file-system \
    --region $AWS_REGION \
    --output json \
    --file-system-type OPENZFS \
    --storage-capacity 1024 \
    --storage-type SSD \
    --subnet-ids $SUBNET_3_ID \
    --security-group-ids $SECURITY_GROUP_ID \
    --open-zfs-configuration "DeploymentType=SINGLE_AZ_1,ThroughputCapacity=4096,RootVolumeConfiguration={DataCompressionType=LZ4},DiskIopsConfiguration={Mode=USER_PROVISIONED,Iops=20000}" \
    --tags Key=Name,Value=Yocto-Poky-Storage-Benchmark-FSX-Open-ZFS Key=owner,Value=cmr \
    | jq '.'

FSX_FILE_SYSTEM_ID=$(aws fsx describe-file-systems \
    --region $AWS_REGION \
    --output json \
    | jq -r '.FileSystems | .[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-FSX-Open-ZFS") | .FileSystemId')

echo "FSx file system id is: $FSX_FILE_SYSTEM_ID"
```

### 2.3 Create the Amazon S3 Bucket for Standard

> NOTE  
> You only have to go through this section, if you want to run the benchmark using S3 Standard!

We create an Amazon S3 Standard bucket as following:
```bash
ACCOUNT_ID=$(aws sts get-caller-identity \
    --query "Account" --output text)

echo "Account ID is: $ACCOUNT_ID"

BENCHMARK_S3_STANDARD_BUCKET_NAME="yocto-poky-benchmark-$ACCOUNT_ID"
echo "S3 Bucket name is: $BENCHMARK_S3_STANDARD_BUCKET_NAME"

aws s3api create-bucket \
    --region $AWS_REGION \
    --bucket $BENCHMARK_S3_STANDARD_BUCKET_NAME \
    | jq '.'
```

### 2.4 Create the Amazon S3 Bucket for Express One Zone

> NOTE  
> You only have to go through this section, if you want to run the benchmark using S3 Express!

We create an Amazon S3 Express bucket in the availability zone 1a. Before we can do this, we have to figure out to which availability zone ID this is mapped in your account:
```bash
AZ_ID=$(aws ec2 describe-availability-zones \
    --region $AWS_REGION \
    | jq -r '.AvailabilityZones[] | select(.ZoneName == "us-east-1a") | .ZoneId')

echo "Availability Zone ID is: $AZ_ID"

ACCOUNT_ID=$(aws sts get-caller-identity \
    --query "Account" --output text)

echo "Account ID is: $ACCOUNT_ID"

BENCHMARK_S3_EXPRESS_BUCKET_NAME="yocto-poky-benchmark-$ACCOUNT_ID--$AZ_ID--x-s3"
echo "S3 Bucket name is: $BENCHMARK_S3_EXPRESS_BUCKET_NAME"

aws s3api create-bucket \
    --region $AWS_REGION \
    --bucket $BENCHMARK_S3_EXPRESS_BUCKET_NAME \
    --create-bucket-configuration "Location={Type=AvailabilityZone,Name=$AZ_ID},Bucket={DataRedundancy=SingleAvailabilityZone,Type=Directory}" \
    | jq '.'
```


## 3 Build the generic [Amazon EC2](https://aws.amazon.com/ec2/) Amazon Machine Image (AMI), we will use for the benchmark

As base image, we use the latest Ubuntu 22.04 LTS image, available in our region.  
Generic AMI means we will install all the linux binaries we need to use EFS, FSx for OpenZFS and S3 Mountpoint.  
Beside installing some Linux utilities and Docker, we also build our Docker image, so that it's available locally in our AMI. This saves us time downloading the Docker image for each execution in a newly created EC2 instance:

First, let's get the latest Ubuntu 22.04 base AMI (for x86):
```bash
UBUNTU_BASE_AMI=$(aws ec2 describe-images \
    --region $AWS_REGION \
    --output text \
    --owners amazon \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
    --query 'sort_by(Images,&CreationDate)[-1].ImageId')
echo "Ubuntu 22.04 base AMI is: $UBUNTU_BASE_AMI"
```

Next, provision the benchmark base AMI:
```bash
aws ec2 run-instances \
    --region $AWS_REGION \
    --output json \
    --image-id $UBUNTU_BASE_AMI \
    --subnet-id $SUBNET_1_ID \
    --instance-type 'm6i.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --count 1 \
    --user-data file://ec2-user-data-script-provision-ec2.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Benchmark-AMI},{Key=owner,Value=cmr}]' \
    | jq '.'

EC2_INSTANCE_ID=$(aws ec2 describe-instances \
    --region $AWS_REGION \
    --filters Name=instance-state-name,Values=running \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-AMI") | .InstanceId')

echo "EC2 instance id is: $EC2_INSTANCE_ID"
```

The setup of this instance will take about 3 minutes. Take a look at [ec2-user-data-script-provision-ec2.txt](ec2-user-data-script-provision-ec2.txt) to understand how we set-up the instance.  

To verify the container creation finished, SSH into the EC2 instance:

```bash
EC2_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region $AWS_REGION \
    --filters Name=instance-state-name,Values=running \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-AMI") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')
echo "EC2 instance public DNS name is: $EC2_INSTANCE_PUBLIC_DNS_NAME"

ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_INSTANCE_PUBLIC_DNS_NAME
```

Run the following command to watch the init log:
```bash
tail -f /var/log/cloud-init-output.log
```

If executed successful, you should see an output like this:
```
...
Successfully tagged ubuntu-yocto-image:latest
Cloud-init v. 24.3.1-0ubuntu0~22.04.1 finished at Thu, 26 Dec 2024 13:22:51 +0000. Datasource DataSourceEc2Local.  Up 155.15 seconds
```

Exit `tail` and run the following command to verify, the container exist:
```
sudo docker images
```

You should see the container `ubuntu-yocto-image` created.

```
REPOSITORY           TAG       IMAGE ID       CREATED          SIZE
ubuntu-yocto-image   latest    3d17d924ee4d   5 minutes ago    1.14GB
ubuntu               22.04     58db3edaf2be   9 days ago       77.9MB
```

Type `exit` to leave the EC2 instance again.

After the instance is initialized, we will create a custom AMI based on it:
```bash
aws ec2 create-image \
    --region $AWS_REGION \
    --output json \
    --instance-id $EC2_INSTANCE_ID \
    --name "Ubuntu-22.04-Yocto-Poky-Storage-Benchmark-AMI" \
    --description "Ubuntu-22.04-Yocto-Poky-Storage-Benchmark-AMI" \
    --tag-specifications 'ResourceType=image,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Benchmark-AMI},{Key=owner,Value=cmr}]' \
    --no-reboot \
    | jq -r '.'

EC2_IMAGE_ID=$(aws ec2 describe-images \
    --region $AWS_REGION \
    --owners self \
    | jq -r '.Images[] | select(.Name == "Ubuntu-22.04-Yocto-Poky-Storage-Benchmark-AMI") | .ImageId')

echo "EC2 image id is: $EC2_IMAGE_ID"
```

Let's wait until the creation of this AMI finished (the CLI call will block, until the image becomes available):
```bash
aws ec2 wait image-available \
    --region $AWS_REGION \
    --image-ids $EC2_IMAGE_ID
```

Afterwards, terminate the EC2 instance, as we don't need it anymore:
```bash
aws ec2 terminate-instances \
    --region $AWS_REGION \
    --output json \
    --instance-id $EC2_INSTANCE_ID \
    | jq '.'
```


## 4 Set-up IAM role and instance profile

Now create the necessary IAM role and instance profile, we need to run the benchmark (this example isn't using a least privilege IAM policy for simplicity):

```bash
aws iam create-role \
    --region $AWS_REGION \
    --output json \
    --role-name EC2-Yocto-Poky-Benchmark-Role \
    --assume-role-policy-document file://trust-policy.json \
    | jq '.'

aws iam attach-role-policy \
    --region $AWS_REGION \
    --output json \
    --role-name EC2-Yocto-Poky-Benchmark-Role \
    --policy-arn arn:aws:iam::aws:policy/AdministratorAccess \
    | jq '.'

aws iam create-instance-profile \
    --region $AWS_REGION \
    --output json \
    --instance-profile-name storage-access-ec2-instance-profile \
    | jq '.'

EC2_INSTANCE_PROFILE_ARN=$(aws iam list-instance-profiles \
    --region $AWS_REGION \
    --output json \
    | jq -r '.InstanceProfiles[] | select(.InstanceProfileName == "storage-access-ec2-instance-profile") | .Arn')

echo "EC2 instance profile ARN is: $EC2_INSTANCE_PROFILE_ARN"

aws iam add-role-to-instance-profile \
    --region $AWS_REGION \
    --output json \
    --role-name EC2-Yocto-Poky-Benchmark-Role \
    --instance-profile-name storage-access-ec2-instance-profile \
    | jq '.'
```


## 5 Run the cache population

We are using the `core-image-sato-sdk` recipe, as it is the most demanding ready to use one (7506 recipes as of 26th Dec. 2024).

### 5.1 Run the cache population for EBS

> NOTE  
> You only have to go through this section, if you want to run the benchmark using EBS!

```bash
rm -rf ec2-user-data-script-populate-ebs-cache.txt

cat <<EOF >> ec2-user-data-script-populate-ebs-cache.txt
#!/bin/bash

# Find all the NVME devices
VOLUMES_NAME=\$(find /dev | grep -i 'nvme[0-21]n1$')
for VOLUME in \$VOLUMES_NAME; do
  # Find and set the device name we've set in AWS
  ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '/dev/(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
  if [ ! -z \$ALIAS ]; then
    ln -s \$VOLUME \$ALIAS
  else
    ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
    if [ ! -z \$ALIAS ]; then
      ln -s \$VOLUME /dev/\$ALIAS
    fi
  fi
done

mkfs -t xfs /dev/sdf
mkdir -p /workspace
mount /dev/sdf /workspace
mkdir -p /workspace/build /workspace/tmp

# Mount the EBS volume and chance ownership to ubuntu
echo '### Mount the EBS volume and chance ownership to ubuntu ###'
mkfs -t xfs /dev/sdg
mkdir -p /cache-ebs
mount /dev/sdg /cache-ebs
chown -R ubuntu /cache-ebs
chgrp -R ubuntu /cache-ebs

cat <<POPULATEEBSCACHESCRIPT >> /workspace/build/populate-ebs-cache.sh
#!/bin/bash

cd /workspace
rm -rf poky
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

# https://docs.yoctoproject.org/singleindex.html#replicating-a-build-offline
echo 'WARN_QA:remove = "host-user-contaminated"' >> /workspace/poky/build/conf/local.conf
echo 'DL_DIR = "/cache/yocto_downloads"' >> /workspace/poky/build/conf/local.conf
echo 'BB_GENERATE_MIRROR_TARBALLS = "1"' >> /workspace/poky/build/conf/local.conf


time bitbake core-image-sato-sdk --runall fetch
POPULATEEBSCACHESCRIPT

chown -R ubuntu /workspace
chgrp -R ubuntu /workspace
chmod +x /workspace/build/populate-ebs-cache.sh

# Running the Docker image to populate the EBS cache
echo '### Running the Docker image to populate the EFS cache ###'
sudo -u ubuntu bash -c 'cd ~; docker run --user 1000 --entrypoint /workspace/populate-ebs-cache.sh -v /workspace/build:/workspace -v /workspace/tmp:/tmp -v /cache-ebs:/cache ubuntu-yocto-image'

# Unmounting and detaching the EBS cache
echo '### Unmounting and detaching the EBS cache ###'
umount -d /dev/sdg
TOKEN=\$(curl --silent -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
AWS_REGION=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/region)
aws configure set default.region \$AWS_REGION
EC2_INSTANCE_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
EBS_VOLUME_ID=\$(aws ec2 describe-volumes \
  --region \$AWS_REGION \
  --output json \
  --filters Name=attachment.instance-id,Values=\$EC2_INSTANCE_ID Name=attachment.device,Values=/dev/sdg \
  | jq -r '.Volumes | .[].VolumeId')
aws ec2 detach-volume \
  --region \$AWS_REGION \
  --volume-id \$EBS_VOLUME_ID

# Shutting down the EC2 instance, after the work is done
echo '### Shutting down the EC2 instance, after the work is done ###'
aws ec2 terminate-instances \
  --region \$AWS_REGION \
  --instance-id \$EC2_INSTANCE_ID
EOF
```

We run the EBS cache population as following:
```bash
aws ec2 run-instances \
    --region $AWS_REGION \
    --image-id $EC2_IMAGE_ID \
    --instance-type 'm6i.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --iam-instance-profile Arn=$EC2_INSTANCE_PROFILE_ARN \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' 'DeviceName=/dev/sdf,Ebs={VolumeSize=200,VolumeType=gp3,Encrypted=true}' 'DeviceName=/dev/sdg,Ebs={VolumeSize=20,VolumeType=gp3,Encrypted=true}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --count 1 \
    --user-data file://ec2-user-data-script-populate-ebs-cache.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Populate-EBS-Cache},{Key=owner,Value=cmr}]' 'ResourceType=volume,Tags=[{Key=Name,Value=EBS-Cache}]' \
    | jq '.'
```

If you want to check the progress, you can SSH into the instance...:
```bash
EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region $AWS_REGION \
    --filters Name=instance-state-name,Values=running \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Populate-EBS-Cache") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')
ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME
```

... and tail the `cloud-init-output.log` log file:
```bash
tail -f /var/log/cloud-init-output.log
```

The instance will shut down at the end of the population automatically. There will be an Amazon EBS volume with the name `EBS-Cache` in `available` state.


### 5.2 Run the cache population for EFS

> NOTE  
> You only have to go through this section, if you want to run the benchmark using EFS!

```bash
rm -rf ec2-user-data-script-populate-efs-cache.txt

cat <<EOF >> ec2-user-data-script-populate-efs-cache.txt
#!/bin/bash

# Find all the NVME devices
VOLUMES_NAME=\$(find /dev | grep -i 'nvme[0-21]n1$')
for VOLUME in \$VOLUMES_NAME; do
  # Find and set the device name we've set in AWS
  ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '/dev/(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
  if [ ! -z \$ALIAS ]; then
    ln -s \$VOLUME \$ALIAS
  else
    ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
    if [ ! -z \$ALIAS ]; then
      ln -s \$VOLUME /dev/\$ALIAS
    fi
  fi
done

mkfs -t xfs /dev/sdf
mkdir -p /workspace
mount /dev/sdf /workspace
mkdir -p /workspace/build /workspace/tmp

# Mount the EFS volume and change ownership to ubuntu
echo '### Mount the EFS volume and change ownership to ubuntu ###'
mkdir -p /cache-efs
mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport $EFS_FILE_SYSTEM_ID.efs.$AWS_REGION.amazonaws.com:/ /cache-efs
echo "$EFS_FILE_SYSTEM_ID:/ /cache-efs efs _netdev,noresvport,tls,iam 0 0" | sudo tee --append  /etc/fstab
chown -R ubuntu /cache-efs
chgrp -R ubuntu /cache-efs

cat <<POPULATEEFSCACHESCRIPT >> /workspace/build/populate-efs-cache.sh
#!/bin/bash

cd /workspace
rm -rf poky
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

# https://docs.yoctoproject.org/singleindex.html#replicating-a-build-offline
echo 'WARN_QA:remove = "host-user-contaminated"' >> /workspace/poky/build/conf/local.conf
echo 'DL_DIR = "/cache/yocto_downloads"' >> /workspace/poky/build/conf/local.conf
echo 'BB_GENERATE_MIRROR_TARBALLS = "1"' >> /workspace/poky/build/conf/local.conf

time bitbake core-image-sato-sdk --runall fetch
POPULATEEFSCACHESCRIPT

chown -R ubuntu /workspace
chgrp -R ubuntu /workspace
chmod +x /workspace/build/populate-efs-cache.sh

# Running the Docker image to populate the EFS cache
echo '### Running the Docker image to populate the EFS cache ###'
sudo -u ubuntu bash -c 'cd ~; docker run --user 1000 --entrypoint /workspace/populate-efs-cache.sh -v /workspace/build:/workspace -v /workspace/tmp:/tmp -v /cache-efs:/cache ubuntu-yocto-image'

# Shutting down the EC2 instance, after the work is done
echo '### Shutting down the EC2 instance, after the work is done ###'
TOKEN=\$(curl --silent -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
AWS_REGION=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/region)
EC2_INSTANCE_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws configure set default.region \$AWS_REGION
aws ec2 terminate-instances \
  --region \$AWS_REGION \
  --instance-id \$EC2_INSTANCE_ID
EOF
```

We run the EFS cache population as following:
```bash
aws ec2 run-instances \
    --region $AWS_REGION \
    --image-id $EC2_IMAGE_ID \
    --instance-type 'm6i.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --iam-instance-profile Arn=$EC2_INSTANCE_PROFILE_ARN \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' 'DeviceName=/dev/sdf,Ebs={VolumeSize=200,VolumeType=gp3,Encrypted=true}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --count 1 \
    --user-data file://ec2-user-data-script-populate-efs-cache.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Populate-EFS-Cache},{Key=owner,Value=cmr}]' \
    | jq '.'
```

If you want to check the progress, you can SSH into the instance...:
```bash
EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region $AWS_REGION \
    --filters Name=instance-state-name,Values=running \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Populate-EFS-Cache") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')
ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME
```

... and tail the `cloud-init-output.log` log file:
```bash
tail -f /var/log/cloud-init-output.log
```

The instance will shut down at the end of the population automatically.


### 5.3 Run the cache population for FSx for OpenZFS

> NOTE  
> You only have to go through this section, if you want to run the benchmark using FSx for OpenZFS!

```bash
rm -rf ec2-user-data-script-populate-fsx-zfs-cache.txt

cat <<EOF >> ec2-user-data-script-populate-fsx-zfs-cache.txt
#!/bin/bash

# Find all the NVME devices
VOLUMES_NAME=\$(find /dev | grep -i 'nvme[0-21]n1$')
for VOLUME in \$VOLUMES_NAME; do
  # Find and set the device name we've set in AWS
  ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '/dev/(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
  if [ ! -z \$ALIAS ]; then
    ln -s \$VOLUME \$ALIAS
  else
    ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
    if [ ! -z \$ALIAS ]; then
      ln -s \$VOLUME /dev/\$ALIAS
    fi
  fi
done

mkfs -t xfs /dev/sdf
mkdir -p /workspace
mount /dev/sdf /workspace
mkdir -p /workspace/build /workspace/tmp

# Mount the FSX for OpenZFS volume
echo '### Mount the FSX for OpenZFS volume ###'
mkdir -p /cache-fsx-zfs
mount -t nfs -o nfsvers=3 $FSX_FILE_SYSTEM_ID.fsx.$AWS_REGION.amazonaws.com:/fsx/ /cache-fsx-zfs
echo "$FSX_FILE_SYSTEM_ID.fsx.$AWS_REGION.amazonaws.com:/fsx/ /cache-fsx-zfs nfs nfsver=3 defaults 0 0" | sudo tee --append  /etc/fstab
# ownership from a FSx file system cannot be changed, but user ubuntu can read/write from/to it


cat <<POPULATEFSXZFSCACHESCRIPT >> /workspace/build/populate-fsx-zfs-cache.sh
#!/bin/bash

cd /workspace
rm -rf poky
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

# https://docs.yoctoproject.org/singleindex.html#replicating-a-build-offline
echo 'WARN_QA:remove = "host-user-contaminated"' >> /workspace/poky/build/conf/local.conf
echo 'DL_DIR = "/cache/yocto_downloads"' >> /workspace/poky/build/conf/local.conf
echo 'BB_GENERATE_MIRROR_TARBALLS = "1"' >> /workspace/poky/build/conf/local.conf

time bitbake core-image-sato-sdk --runall fetch
POPULATEFSXZFSCACHESCRIPT

chown -R ubuntu /workspace
chgrp -R ubuntu /workspace
chmod +x /workspace/build/populate-fsx-zfs-cache.sh

# Running the Docker image to populate the FSx for OpenZFS cache
echo '### Running the Docker image to populate the FSx for OpenZFS cache ###'
sudo -u ubuntu bash -c 'cd ~; docker run --user 1000 --entrypoint /workspace/populate-fsx-zfs-cache.sh -v /workspace/build:/workspace -v /workspace/tmp:/tmp -v /cache-fsx-zfs:/cache ubuntu-yocto-image'

# Shutting down the EC2 instance, after the work is done
echo '### Shutting down the EC2 instance, after the work is done ###'
TOKEN=\$(curl --silent -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
AWS_REGION=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/region)
EC2_INSTANCE_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws configure set default.region \$AWS_REGION
aws ec2 terminate-instances \
  --region \$AWS_REGION \
  --instance-id \$EC2_INSTANCE_ID
EOF
```

We run the FSx for OpenZFS cache population as following:
```bash
aws ec2 run-instances \
    --region $AWS_REGION \
    --image-id $EC2_IMAGE_ID \
    --instance-type 'm6i.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --iam-instance-profile Arn=$EC2_INSTANCE_PROFILE_ARN \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' 'DeviceName=/dev/sdf,Ebs={VolumeSize=200,VolumeType=gp3,Encrypted=true}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --count 1 \
    --user-data file://ec2-user-data-script-populate-fsx-zfs-cache.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Populate-FSX-ZFS-Cache},{Key=owner,Value=cmr}]' \
    | jq '.'
```

If you want to check the progress, you can SSH into the instance...:
```bash
EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region $AWS_REGION \
    --filters Name=instance-state-name,Values=running \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Populate-FSX-ZFS-Cache") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')
ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME
```

... and tail the `cloud-init-output.log` log file:
```bash
tail -f /var/log/cloud-init-output.log
```

The instance will shut down at the end of the population automatically.


### 5.4 Run the cache population for S3 Standard

> NOTE  
> You only have to go through this section, if you want to run the benchmark using S3 Standard!

```bash
rm -rf ec2-user-data-script-populate-s3-standard-cache.txt

cat <<EOF >> ec2-user-data-script-populate-s3-standard-cache.txt
#!/bin/bash

# Find all the NVME devices
VOLUMES_NAME=\$(find /dev | grep -i 'nvme[0-21]n1$')
for VOLUME in \$VOLUMES_NAME; do
  # Find and set the device name we've set in AWS
  ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '/dev/(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
  if [ ! -z \$ALIAS ]; then
    ln -s \$VOLUME \$ALIAS
  else
    ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
    if [ ! -z \$ALIAS ]; then
      ln -s \$VOLUME /dev/\$ALIAS
    fi
  fi
done

mkfs -t xfs /dev/sdf
mkdir -p /workspace
mount /dev/sdf /workspace
mkdir -p /workspace/build /workspace/tmp

# Mount the S3 Standard volume
echo '### Mount the S3 Standard volume ###'
mkdir -p /cache-s3-standard
mount-s3 $BENCHMARK_S3_STANDARD_BUCKET_NAME /cache-s3-standard --allow-delete --allow-overwrite --allow-other --uid 1000 --gid 1000

# As S3-Mountpoint doesn't support rename operations yet, we use a temporary directory in our workspace
echo '### As S3-Mountpoint doesn't support rename operations yet, we use a temporary directory in our workspace ###'
mkdir -p /cache-s3-standard-tmp/yocto_downloads/
chown -R ubuntu /cache-s3-standard-tmp
chgrp -R ubuntu /cache-s3-standard-tmp

cat <<POPULATES3STANDARDCACHESCRIPT >> /workspace/build/populate-s3-standard-cache.sh
#!/bin/bash

cd /workspace
rm -rf poky
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

# https://docs.yoctoproject.org/singleindex.html#replicating-a-build-offline
echo 'WARN_QA:remove = "host-user-contaminated"' >> /workspace/poky/build/conf/local.conf
echo 'DL_DIR = "/cache/yocto_downloads/"' >> /workspace/poky/build/conf/local.conf
echo 'BB_GENERATE_MIRROR_TARBALLS = "1"' >> /workspace/poky/build/conf/local.conf

time bitbake core-image-sato-sdk --runonly=fetch
POPULATES3STANDARDCACHESCRIPT

chown -R ubuntu /workspace
chgrp -R ubuntu /workspace
chmod +x /workspace/build/populate-s3-standard-cache.sh

# Running the Docker image to populate the S3 Standard cache
echo '### Running the Docker image to populate the S3 Standard cache ###'
sudo -u ubuntu bash -c 'cd ~; docker run --user 1000 --entrypoint /workspace/populate-s3-standard-cache.sh -v /workspace/build:/workspace -v /workspace/tmp:/tmp -v /cache-s3-standard-tmp:/cache ubuntu-yocto-image'

# Copying the downloaded artifacts to S3 Standard cache
echo '### Copying the downloaded artifacts to S3 Standard cache ###'
cp -r /cache-s3-standard-tmp/* /cache-s3-standard/

# Shutting down the EC2 instance, after the work is done
echo '### Shutting down the EC2 instance, after the work is done ###'
TOKEN=\$(curl --silent -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
AWS_REGION=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/region)
EC2_INSTANCE_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws configure set default.region \$AWS_REGION
aws ec2 terminate-instances \
  --region \$AWS_REGION \
  --instance-id \$EC2_INSTANCE_ID
EOF
```

When run the S3 Standard cache population as following:

```bash
aws ec2 run-instances \
    --region $AWS_REGION \
    --image-id $EC2_IMAGE_ID \
    --instance-type 'm6i.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --iam-instance-profile Arn=$EC2_INSTANCE_PROFILE_ARN \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' 'DeviceName=/dev/sdf,Ebs={VolumeSize=200,VolumeType=gp3,Encrypted=true}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --count 1 \
    --user-data file://ec2-user-data-script-populate-s3-standard-cache.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Populate-S3-Standard-Cache},{Key=owner,Value=cmr}]' \
    | jq '.'
```

If you want to check the progress, you can SSH into the instance...:
```bash
EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region $AWS_REGION \
    --filters Name=instance-state-name,Values=running \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Populate-S3-Standard-Cache") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')
ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME
```

... and tail the `cloud-init-output.log` log file:
```bash
tail -f /var/log/cloud-init-output.log
```

The instance will shut down at the end of the population automatically.
You can check your Amazon S3 Express bucket, which now contains the cached dependencies.


### 5.5 Run the cache population for S3 Express

> NOTE  
> You only have to go through this section, if you want to run the benchmark using S3 Express!

```bash
rm -rf ec2-user-data-script-populate-s3-express-cache.txt

cat <<EOF >> ec2-user-data-script-populate-s3-express-cache.txt
#!/bin/bash

# Find all the NVME devices
VOLUMES_NAME=\$(find /dev | grep -i 'nvme[0-21]n1$')
for VOLUME in \$VOLUMES_NAME; do
  # Find and set the device name we've set in AWS
  ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '/dev/(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
  if [ ! -z \$ALIAS ]; then
    ln -s \$VOLUME \$ALIAS
  else
    ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
    if [ ! -z \$ALIAS ]; then
      ln -s \$VOLUME /dev/\$ALIAS
    fi
  fi
done

mkfs -t xfs /dev/sdf
mkdir -p /workspace
mount /dev/sdf /workspace
mkdir -p /workspace/build /workspace/tmp

# Mount the S3 Express volume and change ownership to ubuntu
echo '### Mount the S3 Express volume and change ownership to ubuntu ###'
mkdir -p /cache-s3-express
mount-s3 $BENCHMARK_S3_EXPRESS_BUCKET_NAME /cache-s3-express --allow-delete --allow-overwrite --allow-other --uid 1000 --gid 1000

# As S3-Mountpoint doesn't support rename operations yet, we use a temporary directory in our workspace
echo '### As S3-Mountpoint doesn't support rename operations yet, we use a temporary directory in our workspace ###'
mkdir -p /cache-s3-express-tmp/yocto_downloads /cache-s3-express-tmp/yocto_shared_state
chown -R ubuntu /cache-s3-express-tmp
chgrp -R ubuntu /cache-s3-express-tmp

cat <<POPULATES3EXPRESSCACHESCRIPT >> /workspace/build/populate-s3-express-cache.sh
#!/bin/bash

cd /workspace
rm -rf poky
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

# https://docs.yoctoproject.org/singleindex.html#replicating-a-build-offline
echo 'WARN_QA:remove = "host-user-contaminated"' >> /workspace/poky/build/conf/local.conf
echo 'DL_DIR = "/cache/yocto_downloads"' >> /workspace/poky/build/conf/local.conf
echo 'BB_GENERATE_MIRROR_TARBALLS = "1"' >> /workspace/poky/build/conf/local.conf

time bitbake core-image-sato-sdk --runall fetch
POPULATES3EXPRESSCACHESCRIPT

chown -R ubuntu /workspace
chgrp -R ubuntu /workspace
chmod +x /workspace/build/populate-s3-express-cache.sh

# Running the Docker image to populate the S3 Express cache
echo '### Running the Docker image to populate the S3 Express cache ###'
sudo -u ubuntu bash -c 'cd ~; docker run --user 1000 --entrypoint /workspace/populate-s3-express-cache.sh -v /workspace/build:/workspace -v /workspace/tmp:/tmp -v /cache-s3-express-tmp:/cache ubuntu-yocto-image'

# Copying the downloaded artifacts to S3 Express cache
echo '### Copying the downloaded artifacts to S3 Express cache ###'
cp -r /cache-s3-express-tmp/* /cache-s3-express/

# Shutting down the EC2 instance, after the work is done
echo '### Shutting down the EC2 instance, after the work is done ###'
TOKEN=\$(curl --silent -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
AWS_REGION=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/region)
EC2_INSTANCE_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws configure set default.region \$AWS_REGION
aws ec2 terminate-instances \
  --region \$AWS_REGION \
  --instance-id \$EC2_INSTANCE_ID
EOF
```

When run the S3 Standard cache population as following:

```bash
aws ec2 run-instances \
    --region $AWS_REGION \
    --image-id $EC2_IMAGE_ID \
    --instance-type 'm6i.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --iam-instance-profile Arn=$EC2_INSTANCE_PROFILE_ARN \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' 'DeviceName=/dev/sdf,Ebs={VolumeSize=200,VolumeType=gp3,Encrypted=true}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --count 1 \
    --user-data file://ec2-user-data-script-populate-s3-express-cache.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Populate-S3-Express-Cache},{Key=owner,Value=cmr}]' \
    | jq '.'
```

If you want to check the progress, you can SSH into the instance...:
```bash
EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region $AWS_REGION \
    --filters Name=instance-state-name,Values=running \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Populate-S3-Express-Cache") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')

ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME
```

... and tail the `cloud-init-output.log` log file:
```bash
tail -f /var/log/cloud-init-output.log
```

The instance will shut down at the end of the population automatically.
You can check your Amazon S3 Express bucket, which now contains the cached dependencies.


## 6 Run the benchmarks

We are using the `core-image-sato-sdk` recipe, as it is the most demanding ready to use one (7506 recipes as of 26th Dec. 2024).

### 6.1 Run the benchmark for EBS

> NOTE  
> You only have to go through this section, if you want to run the benchmark using EBS!

```bash
rm -rf ec2-user-data-script-benchmark-ebs-cache.txt

cat <<EOF >> ec2-user-data-script-benchmark-ebs-cache.txt
#!/bin/bash

# Attach the EBS cache volume
echo '### Attach the EBS cache volume ###'
TOKEN=\$(curl --silent -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
AWS_REGION=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/region)
EC2_INSTANCE_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
EBS_VOLUME_ID=\$(aws ec2 describe-volumes \
  --region \$AWS_REGION \
  --output json \
  --filters Name=tag:Name,Values=EBS-Cache | jq -r '.Volumes | .[].VolumeId')
aws ec2 attach-volume \
  --region \$AWS_REGION \
  --instance-id \$EC2_INSTANCE_ID \
  --device /dev/sdg \
  --volume-id \$EBS_VOLUME_ID

sleep 5

# Find all the NVME devices
VOLUMES_NAME=\$(find /dev | grep -i 'nvme[0-21]n1$')
for VOLUME in \$VOLUMES_NAME; do
  # Find and set the device name we've set in AWS
  ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '/dev/(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
  if [ ! -z \$ALIAS ]; then
    ln -s \$VOLUME \$ALIAS
  else
    ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
    if [ ! -z \$ALIAS ]; then
      ln -s \$VOLUME /dev/\$ALIAS
    fi
  fi
done

mkfs -t xfs /dev/sdf
mkdir -p /workspace
mount /dev/sdf /workspace
mkdir -p /workspace/build /workspace/tmp

# Mount the EBS volume and chance ownership to ubuntu
echo '### Mount the EBS volume and chance ownership to ubuntu ###'
mkdir -p /cache-ebs
mount /dev/sdg /cache-ebs
chown ubuntu /cache-ebs
chgrp ubuntu /cache-ebs


cat <<BENCHMARKEBSCACHESCRIPT >> /workspace/build/benchmark-ebs-cache.sh
#!/bin/bash

cd /workspace
rm -rf poky
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

# https://docs.yoctoproject.org/singleindex.html#replicating-a-build-offline
echo 'WARN_QA:remove = "host-user-contaminated"' >> /workspace/poky/build/conf/local.conf
echo 'SSTATE_DIR = "/cache/yocto_shared_state/"' >> /workspace/poky/build/conf/local.conf
echo 'SOURCE_MIRROR_URL ?= "file:////cache/yocto_downloads/"' >> /workspace/poky/build/conf/local.conf
echo 'INHERIT += "own-mirrors"' >> /workspace/poky/build/conf/local.conf
echo 'BB_NO_NETWORK = "1"' >> /workspace/poky/build/conf/local.conf

time bitbake core-image-sato-sdk
BENCHMARKEBSCACHESCRIPT

chown -R ubuntu /workspace
chgrp -R ubuntu /workspace
chmod +x /workspace/build/benchmark-ebs-cache.sh

# Running the Docker image to benchmark the EBS cache
echo '### Running the Docker image to benchmark the EBS cache ###'
sudo -u ubuntu bash -c 'cd ~; docker run --user 1000 --entrypoint /workspace/benchmark-ebs-cache.sh -v /workspace/build:/workspace -v /workspace/tmp:/tmp -v /cache-ebs:/cache ubuntu-yocto-image'

# Uploading the benchmark results to S3
echo '### Uploading the benchmark results to S3 ###'
TOKEN=\$(curl --silent -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
AWS_REGION=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/region)
EC2_INSTANCE_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
EC2_AZ_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/availability-zone)
aws configure set default.region \$AWS_REGION
egrep '^real.+s$' /var/log/cloud-init-output.log | tail -1 > benchmark.txt
aws s3 cp \
    --region \$AWS_REGION \
    benchmark.txt s3://$S3_BUCKET_NAME/ebs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-benchmark.txt
aws s3 cp \
    --region \$AWS_REGION \
    /var/log/cloud-init-output.log s3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-cloud-init-output.log

# Uploading the sysstat metrics to S3
echo '### Uploading the sysstat metrics to S3 ###'
aws s3 cp \
    --region \$AWS_REGION \
    /var/log/sysstat/* s3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID/

# Shutting down the EC2 instance, after the work is done
echo '### Shutting down the EC2 instance, after the work is done ###'
aws ec2 terminate-instances \
  --region \$AWS_REGION \
  --instance-id \$EC2_INSTANCE_ID
EOF
```

We run the EBS benchmark in the same availability zone, where the EBS cache volume is:
```bash
EBS_VOLUME_AZ_ID=$(aws ec2 describe-volumes \
  --region $AWS_REGION \
  --output json \
  --filters Name=tag:Name,Values=EBS-Cache | jq -r '.Volumes | .[].AvailabilityZone')
echo "EBS cache volume AZ is: $EBS_VOLUME_AZ_ID"

EBS_SUBNET_ID=$(aws ec2 describe-subnets \
  --region $AWS_REGION \
  --output json \
  --filter Name=availability-zone,Values=$EBS_VOLUME_AZ_ID Name=default-for-az,Values=true | jq -r '.Subnets | .[].SubnetId')
echo "EC2 subnet to use for EBS cache volume is: $EBS_SUBNET_ID"

aws ec2 run-instances \
    --region $AWS_REGION \
    --subnet-id  $EBS_SUBNET_ID \
    --image-id $EC2_IMAGE_ID \
    --instance-type 'm6i.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --iam-instance-profile Arn=$EC2_INSTANCE_PROFILE_ARN \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' 'DeviceName=/dev/sdf,Ebs={VolumeSize=200,VolumeType=gp3,Encrypted=true}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --count 1 \
    --user-data file://ec2-user-data-script-benchmark-ebs-cache.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Benchmark-EBS-Cache},{Key=owner,Value=cmr}]' \
    | jq '.'
```

If you want to check the progress, you can SSH into the instance...:
```bash
EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region $AWS_REGION \
    --filters Name=instance-state-name,Values=running \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-EBS-Cache") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')
ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME
```

... and tail the `cloud-init-output.log` log file:
```bash
tail -f /var/log/cloud-init-output.log
```


### 6.2 Run the benchmark for EFS

> NOTE  
> You only have to go through this section, if you want to run the benchmark using EFS!

```bash
rm -rf ec2-user-data-script-benchmark-efs-cache.txt

cat <<EOF >> ec2-user-data-script-benchmark-efs-cache.txt
#!/bin/bash

# Find all the NVME devices
VOLUMES_NAME=\$(find /dev | grep -i 'nvme[0-21]n1$')
for VOLUME in \$VOLUMES_NAME; do
  # Find and set the device name we've set in AWS
  ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '/dev/(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
  if [ ! -z \$ALIAS ]; then
    ln -s \$VOLUME \$ALIAS
  else
    ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
    if [ ! -z \$ALIAS ]; then
      ln -s \$VOLUME /dev/\$ALIAS
    fi
  fi
done

mkfs -t xfs /dev/sdf
mkdir -p /workspace
mount /dev/sdf /workspace
mkdir -p /workspace/build /workspace/tmp

# Mount the EFS volume and change ownership to ubuntu
echo '### Mount the EFS volume and change ownership to ubuntu ###'
mkdir -p /cache-efs
mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport $EFS_FILE_SYSTEM_ID.efs.$AWS_REGION.amazonaws.com:/ /cache-efs
echo "$EFS_FILE_SYSTEM_ID:/ /cache-efs efs _netdev,noresvport,tls,iam 0 0" | sudo tee --append  /etc/fstab
chown ubuntu /cache-efs
chgrp ubuntu /cache-efs


cat <<BENCHMARKEFSCACHESCRIPT >> /workspace/build/benchmark-efs-cache.sh
#!/bin/bash

cd /workspace
rm -rf poky
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

# https://docs.yoctoproject.org/singleindex.html#replicating-a-build-offline
echo 'WARN_QA:remove = "host-user-contaminated"' >> /workspace/poky/build/conf/local.conf
echo 'SSTATE_DIR = "/cache/yocto_shared_state/"' >> /workspace/poky/build/conf/local.conf
echo 'SOURCE_MIRROR_URL ?= "file:////cache/yocto_downloads/"' >> /workspace/poky/build/conf/local.conf
echo 'INHERIT += "own-mirrors"' >> /workspace/poky/build/conf/local.conf
echo 'BB_NO_NETWORK = "1"' >> /workspace/poky/build/conf/local.conf

time bitbake core-image-sato-sdk
BENCHMARKEFSCACHESCRIPT

chown -R ubuntu /workspace
chgrp -R ubuntu /workspace
chmod +x /workspace/build/benchmark-efs-cache.sh

# Running the Docker image to benchmark the EFS cache
echo '### Running the Docker image to benchmark the EFS cache ###'
sudo -u ubuntu bash -c 'cd ~; docker run --user 1000 --entrypoint /workspace/benchmark-efs-cache.sh -v /workspace/build:/workspace -v /workspace/tmp:/tmp -v /cache-efs:/cache ubuntu-yocto-image'

# Uploading the benchmark results to S3
echo '### Uploading the benchmark results to S3 ###'
TOKEN=\$(curl --silent -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
AWS_REGION=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/region)
EC2_INSTANCE_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
EC2_AZ_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/availability-zone)
aws configure set default.region \$AWS_REGION
egrep '^real.+s$' /var/log/cloud-init-output.log | tail -1 > benchmark.txt
aws s3 cp \
    --region \$AWS_REGION \
    benchmark.txt s3://$S3_BUCKET_NAME/fsx/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-benchmark.txt
aws s3 cp \
    --region \$AWS_REGION \
    /var/log/cloud-init-output.log s3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-cloud-init-output.log

# Uploading the sysstat metrics to S3
echo '### Uploading the sysstat metrics to S3 ###'
aws s3 cp \
    --region \$AWS_REGION \
    /var/log/sysstat/* s3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID/

# Shutting down the EC2 instance, after the work is done
echo '### Shutting down the EC2 instance, after the work is done ###'
aws ec2 terminate-instances \
  --region \$AWS_REGION \
  --instance-id \$EC2_INSTANCE_ID
EOF
```

We run the EFS benchmark as following:
```bash
aws ec2 run-instances \
    --region $AWS_REGION \
    --image-id $EC2_IMAGE_ID \
    --instance-type 'm6i.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --iam-instance-profile Arn=$EC2_INSTANCE_PROFILE_ARN \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' 'DeviceName=/dev/sdf,Ebs={VolumeSize=200,VolumeType=gp3,Encrypted=true}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --count 1 \
    --user-data file://ec2-user-data-script-benchmark-efs-cache.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Benchmark-EFS-Cache},{Key=owner,Value=cmr}]' \
    | jq '.'
```

If you want to check the progress, you can SSH into the instance...:
```bash
EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region $AWS_REGION \
    --filters Name=instance-state-name,Values=running \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-EFS-Cache") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')
ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME
```

... and tail the `cloud-init-output.log` log file:
```bash
tail -f /var/log/cloud-init-output.log
```


### 6.3 Run the benchmark for FSx for OpenZFS

> NOTE  
> You only have to go through this section, if you want to run the benchmark using FSx for OpenZFS!

```bash
rm -rf ec2-user-data-script-benchmark-fsx-zfs-cache.txt

cat <<EOF >> ec2-user-data-script-benchmark-fsx-zfs-cache.txt
#!/bin/bash

# Find all the NVME devices
VOLUMES_NAME=\$(find /dev | grep -i 'nvme[0-21]n1$')
for VOLUME in \$VOLUMES_NAME; do
  # Find and set the device name we've set in AWS
  ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '/dev/(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
  if [ ! -z \$ALIAS ]; then
    ln -s \$VOLUME \$ALIAS
  else
    ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
    if [ ! -z \$ALIAS ]; then
      ln -s \$VOLUME /dev/\$ALIAS
    fi
  fi
done

mkfs -t xfs /dev/sdf
mkdir -p /workspace
mount /dev/sdf /workspace
mkdir -p /workspace/build /workspace/tmp

# Mount the FSX for OpenZFS volume
echo '### Mount the FSX for OpenZFS volume ###'
mkdir -p /cache-fsx-zfs
mount -t nfs -o nfsvers=3 $FSX_FILE_SYSTEM_ID.fsx.$AWS_REGION.amazonaws.com:/fsx/ /cache-fsx-zfs
echo "$FSX_FILE_SYSTEM_ID.fsx.$AWS_REGION.amazonaws.com:/fsx/ /cache-fsx-zfs nfs nfsver=3 defaults 0 0" | sudo tee --append  /etc/fstab
# ownership from a FSx file system cannot be changed, but user ubuntu can read/write from/to it


cat <<BENCHMARKFSXZFSCACHESCRIPT >> /workspace/build/benchmark-fsx-zfs-cache.sh
#!/bin/bash

cd /workspace
rm -rf poky
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

# https://docs.yoctoproject.org/singleindex.html#replicating-a-build-offline
echo 'WARN_QA:remove = "host-user-contaminated"' >> /workspace/poky/build/conf/local.conf
echo 'SSTATE_DIR = "/cache/yocto_shared_state/"' >> /workspace/poky/build/conf/local.conf
echo 'SOURCE_MIRROR_URL ?= "file:////cache/yocto_downloads/"' >> /workspace/poky/build/conf/local.conf
echo 'INHERIT += "own-mirrors"' >> /workspace/poky/build/conf/local.conf
echo 'BB_NO_NETWORK = "1"' >> /workspace/poky/build/conf/local.conf

time bitbake core-image-sato-sdk
BENCHMARKFSXZFSCACHESCRIPT

chown -R ubuntu /workspace
chgrp -R ubuntu /workspace
chmod +x /workspace/build/benchmark-fsx-zfs-cache.sh

# Running the Docker image to benchmark the FSx for OpenZFS cache
echo '### Running the Docker image to benchmark the FSx for OpenZFS cache ###'
sudo -u ubuntu bash -c 'cd ~; docker run --user 1000 --entrypoint /workspace/benchmark-fsx-zfs-cache.sh -v /workspace/build:/workspace -v /workspace/tmp:/tmp -v /cache-fsx-zfs:/cache ubuntu-yocto-image'

# Uploading the benchmark results to S3
echo '### Uploading the benchmark results to S3 ###'
TOKEN=\$(curl --silent -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
AWS_REGION=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/region)
EC2_INSTANCE_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
EC2_AZ_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/availability-zone)
aws configure set default.region \$AWS_REGION
egrep '^real.+s$' /var/log/cloud-init-output.log | tail -1 > benchmark.txt
aws s3 cp \
    --region \$AWS_REGION \
    benchmark.txt s3://$S3_BUCKET_NAME/fsx/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-benchmark.txt
aws s3 cp \
    --region \$AWS_REGION \
    /var/log/cloud-init-output.log s3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-cloud-init-output.log

# Uploading the sysstat metrics to S3
echo '### Uploading the sysstat metrics to S3 ###'
aws s3 cp \
    --region \$AWS_REGION \
    /var/log/sysstat/* s3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID/

# Shutting down the EC2 instance, after the work is done
echo '### Shutting down the EC2 instance, after the work is done ###'
aws ec2 terminate-instances \
  --region \$AWS_REGION \
  --instance-id \$EC2_INSTANCE_ID
EOF
```

We run the FSx for OpenZFS benchmark as following:
```bash
aws ec2 run-instances \
    --region $AWS_REGION \
    --image-id $EC2_IMAGE_ID \
    --instance-type 'm6i.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --iam-instance-profile Arn=$EC2_INSTANCE_PROFILE_ARN \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' 'DeviceName=/dev/sdf,Ebs={VolumeSize=200,VolumeType=gp3,Encrypted=true}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --count 1 \
    --user-data file://ec2-user-data-script-benchmark-fsx-zfs-cache.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Benchmark-FSx-ZFS-Cache},{Key=owner,Value=cmr}]' \
    | jq '.'
```

If you want to check the progress, you can SSH into the instance...:
```bash
EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region $AWS_REGION \
    --filters Name=instance-state-name,Values=running \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-FSx-ZFS-Cache") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')
ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME
```

... and tail the `cloud-init-output.log` log file:
```bash
tail -f /var/log/cloud-init-output.log
```


### 6.4 Run the benchmark for S3 Standard

> NOTE  
> You only have to go through this section, if you want to run the benchmark using S3 Standard!

```bash
rm -rf ec2-user-data-script-benchmark-s3-standard-cache.txt

cat <<EOF >> ec2-user-data-script-benchmark-s3-standard-cache.txt
#!/bin/bash

# Find all the NVME devices
VOLUMES_NAME=\$(find /dev | grep -i 'nvme[0-21]n1$')
for VOLUME in \$VOLUMES_NAME; do
  # Find and set the device name we've set in AWS
  ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '/dev/(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
  if [ ! -z \$ALIAS ]; then
    ln -s \$VOLUME \$ALIAS
  else
    ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
    if [ ! -z \$ALIAS ]; then
      ln -s \$VOLUME /dev/\$ALIAS
    fi
  fi
done

mkfs -t xfs /dev/sdf
mkdir -p /workspace
mount /dev/sdf /workspace
mkdir -p /workspace/build /workspace/tmp

# Mount the S3 Standard volume
echo '### Mount the S3 Express volume ###'
mkdir -p /cache-s3-standard

mount-s3 $BENCHMARK_S3_STANDARD_BUCKET_NAME /cache-s3-standard --allow-delete --allow-overwrite --allow-other --uid 1000 --gid 1000

cat <<BENCHMARKS3STANDARDCACHESCRIPT >> /workspace/build/benchmark-s3-standard-cache.sh
#!/bin/bash

cd /workspace
rm -rf poky
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

# https://docs.yoctoproject.org/singleindex.html#replicating-a-build-offline
echo 'WARN_QA:remove = "host-user-contaminated"' >> /workspace/poky/build/conf/local.conf
# using a shared state cache with S3 Mountpoints is failing
#echo 'SSTATE_DIR = "/cache/yocto_shared_state/"' >> /workspace/poky/build/conf/local.conf
echo 'SOURCE_MIRROR_URL ?= "file:////cache/yocto_downloads/"' >> /workspace/poky/build/conf/local.conf
echo 'INHERIT += "own-mirrors"' >> /workspace/poky/build/conf/local.conf
echo 'BB_NO_NETWORK = "1"' >> /workspace/poky/build/conf/local.conf

time bitbake core-image-sato-sdk
BENCHMARKS3STANDARDCACHESCRIPT

chown -R ubuntu /workspace
chgrp -R ubuntu /workspace
chmod +x /workspace/build/benchmark-s3-standard-cache.sh

# Running the Docker image to benchmark the S3 Standard cache
echo '### Running the Docker image to benchmark the S3 Standard cache ###'
sudo -u ubuntu bash -c 'cd ~; docker run --user 1000 --entrypoint /workspace/benchmark-s3-standard-cache.sh -v /workspace/build:/workspace -v /workspace/tmp:/tmp -v /cache-s3-standard:/cache ubuntu-yocto-image'

# Uploading the benchmark results to S3
echo '### Uploading the benchmark results to S3 ###'
TOKEN=\$(curl --silent -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
AWS_REGION=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/region)
EC2_INSTANCE_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
EC2_AZ_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/availability-zone)
aws configure set default.region \$AWS_REGION
egrep '^real.+s$' /var/log/cloud-init-output.log | tail -1 > benchmark.txt
aws s3 cp \
    --region \$AWS_REGION \
    benchmark.txt s3://$S3_BUCKET_NAME/s3/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-benchmark.txt
aws s3 cp \
    --region \$AWS_REGION \
    /var/log/cloud-init-output.log s3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-cloud-init-output.log

# Uploading the sysstat metrics to S3
echo '### Uploading the sysstat metrics to S3 ###'
aws s3 cp \
    --region \$AWS_REGION \
    /var/log/sysstat/* s3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID/

# Shutting down the EC2 instance, after the work is done
echo '### Shutting down the EC2 instance, after the work is done ###'
aws ec2 terminate-instances \
  --region \$AWS_REGION \
  --instance-id \$EC2_INSTANCE_ID
EOF
```

We run the S3 Standard benchmark as following:
```bash
aws ec2 run-instances \
    --region $AWS_REGION \
    --image-id $EC2_IMAGE_ID \
    --instance-type 'm6i.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --iam-instance-profile Arn=$EC2_INSTANCE_PROFILE_ARN \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' 'DeviceName=/dev/sdf,Ebs={VolumeSize=200,VolumeType=gp3,Encrypted=true}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --count 1 \
    --user-data file://ec2-user-data-script-benchmark-s3-standard-cache.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Benchmark-S3-Standard-Cache},{Key=owner,Value=cmr}]' \
    | jq '.'
```

If you want to check the progress, you can SSH into the instance...:
```bash
EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region $AWS_REGION \
    --filters Name=instance-state-name,Values=running \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-S3-Standard-Cache") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')
ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME
```

... and tail the `cloud-init-output.log` log file:
```bash
tail -f /var/log/cloud-init-output.log
```


### 6.5 Run the benchmark for S3 Express

> NOTE  
> You only have to go through this section, if you want to run the benchmark using S3 Express!

```bash
rm -rf ec2-user-data-script-benchmark-s3-express-cache.txt

cat <<EOF >> ec2-user-data-script-benchmark-s3-express-cache.txt
#!/bin/bash

# Find all the NVME devices
VOLUMES_NAME=\$(find /dev | grep -i 'nvme[0-21]n1$')
for VOLUME in \$VOLUMES_NAME; do
  # Find and set the device name we've set in AWS
  ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '/dev/(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
  if [ ! -z \$ALIAS ]; then
    ln -s \$VOLUME \$ALIAS
  else
    ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
    if [ ! -z \$ALIAS ]; then
      ln -s \$VOLUME /dev/\$ALIAS
    fi
  fi
done

mkfs -t xfs /dev/sdf
mkdir -p /workspace
mount /dev/sdf /workspace
mkdir -p /workspace/build /workspace/tmp

# Mount the S3 Express volume and change ownership to ubuntu
echo '### Mount the S3 Express volume and change ownership to ubuntu ###'
mkdir -p /cache-s3-express

mount-s3 $BENCHMARK_S3_EXPRESS_BUCKET_NAME /cache-s3-express --allow-delete --allow-overwrite --allow-other --uid 1000 --gid 1000

cat <<BENCHMARKS3EXPRESSCACHESCRIPT >> /workspace/build/benchmark-s3-express-cache.sh
#!/bin/bash

cd /workspace
rm -rf poky
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

# https://docs.yoctoproject.org/singleindex.html#replicating-a-build-offline
echo 'WARN_QA:remove = "host-user-contaminated"' >> /workspace/poky/build/conf/local.conf
# using a shared state cache with S3 Mountpoints is failing
#echo 'SSTATE_DIR = "/cache/yocto_shared_state/"' >> /workspace/poky/build/conf/local.conf
echo 'SOURCE_MIRROR_URL ?= "file:////cache/yocto_downloads/"' >> /workspace/poky/build/conf/local.conf
echo 'INHERIT += "own-mirrors"' >> /workspace/poky/build/conf/local.conf
echo 'BB_NO_NETWORK = "1"' >> /workspace/poky/build/conf/local.conf

time bitbake core-image-sato-sdk
BENCHMARKS3EXPRESSCACHESCRIPT

chown -R ubuntu /workspace
chgrp -R ubuntu /workspace
chmod +x /workspace/build/benchmark-s3-express-cache.sh

# Running the Docker image to benchmark the S3 Express cache
echo '### Running the Docker image to populate the S3 Express cache ###'
sudo -u ubuntu bash -c 'cd ~; docker run --user 1000 --entrypoint /workspace/benchmark-s3-express-cache.sh -v /workspace/build:/workspace -v /workspace/tmp:/tmp -v /cache-s3-express:/cache ubuntu-yocto-image'

# Uploading the benchmark results to S3
echo '### Uploading the benchmark results to S3 ###'
TOKEN=\$(curl --silent -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
AWS_REGION=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/region)
EC2_INSTANCE_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
EC2_AZ_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/availability-zone)
aws configure set default.region \$AWS_REGION
egrep '^real.+s$' /var/log/cloud-init-output.log | tail -1 > benchmark.txt
aws s3 cp \
    --region \$AWS_REGION \
    benchmark.txt s3://$S3_BUCKET_NAME/s3/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-benchmark.txt
aws s3 cp \
    --region \$AWS_REGION \
    /var/log/cloud-init-output.log s3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-cloud-init-output.log

# Uploading the sysstat metrics to S3
echo '### Uploading the sysstat metrics to S3 ###'
aws s3 cp \
    --region \$AWS_REGION \
    '/var/log/sysstat/*' 's3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID/'

# Shutting down the EC2 instance, after the work is done
echo '### Shutting down the EC2 instance, after the work is done ###'
aws ec2 terminate-instances \
  --region \$AWS_REGION \
  --instance-id \$EC2_INSTANCE_ID
EOF
```

We run the S3 Express benchmark as following:
```bash
aws ec2 run-instances \
    --region $AWS_REGION \
    --image-id $EC2_IMAGE_ID \
    --instance-type 'm6i.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --iam-instance-profile Arn=$EC2_INSTANCE_PROFILE_ARN \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' 'DeviceName=/dev/sdf,Ebs={VolumeSize=200,VolumeType=gp3,Encrypted=true}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --count 1 \
    --user-data file://ec2-user-data-script-benchmark-s3-express-cache.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Benchmark-S3-Express-Cache},{Key=owner,Value=cmr}]' \
    | jq '.'
```

If you want to check the progress, you can SSH into the instance...:
```bash
EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region $AWS_REGION \
    --filters Name=instance-state-name,Values=running \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-S3-Express-Cache") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')
ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME
```

... and tail the `cloud-init-output.log` log file:
```bash
tail -f /var/log/cloud-init-output.log
```


## 7 Benchmark EC2 with [NVMe](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/InstanceStorage.html)

### 7.1 Run the benchmark for EBS

> NOTE  
> You only have to go through this section, if you want to run the benchmark using an NVMe instance!

```bash
rm -rf ec2-user-data-script-benchmark-nvme-cache.txt

cat <<EOF >> ec2-user-data-script-benchmark-nvme-cache.txt
#!/bin/bash

# Find all the NVME devices
VOLUMES_NAME=\$(find /dev | grep -i 'nvme[0-21]n1$')
for VOLUME in \$VOLUMES_NAME; do
  # Find and set the device name we've set in AWS
  ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '/dev/(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
  if [ ! -z \$ALIAS ]; then
    ln -s \$VOLUME \$ALIAS
  else
    ALIAS=\$(nvme id-ctrl -v \$VOLUME | grep -Po '0000:.*$' | grep -Po '(sda1|xvda|sd[b-z][1-15]?|xvd[b-z])')
    if [ ! -z \$ALIAS ]; then
      ln -s \$VOLUME /dev/\$ALIAS
    fi
  fi
done

mkfs -t xfs /dev/sdb
mkdir -p /workspace
mount /dev/sdb /workspace
mkdir -p /workspace/build /workspace/tmp

# Mount the EFS volume and change ownership to ubuntu
echo '### Mount the EFS volume and change ownership to ubuntu ###'
mkdir -p /cache-efs
mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport $EFS_FILE_SYSTEM_ID.efs.$AWS_REGION.amazonaws.com:/ /cache-efs
echo "$EFS_FILE_SYSTEM_ID:/ /cache-efs efs _netdev,noresvport,tls,iam 0 0" | sudo tee --append  /etc/fstab
chown -R ubuntu /cache-efs
chgrp -R ubuntu /cache-efs


cat <<BENCHMARKNVMECACHESCRIPT >> /workspace/build/benchmark-nvme-cache.sh
#!/bin/bash

cd /workspace
rm -rf poky
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

# https://docs.yoctoproject.org/singleindex.html#replicating-a-build-offline
echo 'WARN_QA:remove = "host-user-contaminated"' >> /workspace/poky/build/conf/local.conf
echo 'SOURCE_MIRROR_URL ?= "file:////cache/"' >> /workspace/poky/build/conf/local.conf
echo 'INHERIT += "own-mirrors"' >> /workspace/poky/build/conf/local.conf
echo 'BB_NO_NETWORK = "1"' >> /workspace/poky/build/conf/local.conf

time bitbake core-image-sato-sdk
BENCHMARKNVMECACHESCRIPT

chown -R ubuntu /workspace
chgrp -R ubuntu /workspace
chmod +x /workspace/build/benchmark-nvme-cache.sh

# Running the Docker image to benchmark the NVME instance
echo '### Running the Docker image to benchmark the NVME instance ###'
sudo -u ubuntu bash -c 'cd ~; docker run --user 1000 --entrypoint /workspace/benchmark-nvme-cache.sh -v /workspace/build:/workspace -v /workspace/tmp:/tmp -v /cache-efs:/cache ubuntu-yocto-image'

# Uploading the benchmark results to S3
echo '### Uploading the benchmark results to S3 ###'
TOKEN=\$(curl --silent -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
AWS_REGION=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/region)
EC2_INSTANCE_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
EC2_AZ_ID=\$(curl --silent -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/placement/availability-zone)
aws configure set default.region \$AWS_REGION
egrep '^real.+s$' /var/log/cloud-init-output.log | tail -1 > benchmark.txt
aws s3 cp \
    --region \$AWS_REGION \
    benchmark.txt s3://$S3_BUCKET_NAME/nvme/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-benchmark.txt
aws s3 cp \
    --region \$AWS_REGION \
    /var/log/cloud-init-output.log s3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-cloud-init-output.log

# Uploading the sysstat metrics to S3
echo '### Uploading the sysstat metrics to S3 ###'
aws s3 cp \
    --region \$AWS_REGION \
    /var/log/sysstat/* s3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID/

# Shutting down the EC2 instance, after the work is done
echo '### Shutting down the EC2 instance, after the work is done ###'
aws ec2 terminate-instances \
  --region \$AWS_REGION \
  --instance-id \$EC2_INSTANCE_ID
EOF
```

We run the NVMe benchmark as following:
```bash
aws ec2 run-instances \
    --region $AWS_REGION \
    --image-id $EC2_IMAGE_ID \
    --instance-type 'm6id.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --iam-instance-profile Arn=$EC2_INSTANCE_PROFILE_ARN \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --count 1 \
    --user-data file://ec2-user-data-script-benchmark-nvme-cache.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Benchmark-NVMe-Cache},{Key=owner,Value=cmr}]' \
    | jq '.'
```

If you want to check the progress, you can SSH into the instance...:
```bash
EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region $AWS_REGION \
    --filters Name=instance-state-name,Values=running \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-NVMe-Cache") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')
ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME
```

... and tail the `cloud-init-output.log` log file:
```bash
tail -f /var/log/cloud-init-output.log
```