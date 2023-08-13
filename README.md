# Benchmark the performance and throughput for [Amazon EBS](https://aws.amazon.com/ebs/), [Amazon EFS](https://aws.amazon.com/efs) and [Amazon FSx for Open ZFS](https://aws.amazon.com/fsx/openzfs/), when running hundreds of Yocto Linux builds in parallel

## 1 Setup

Following setup was selected:
- AWS region: Frankfurt (us-east-1)
- OS: Ubuntu 22.04 LTS release as base image
- all file systems are encrypted with the default service KMS key, except for the instance root volume (because it doesn't contain sensitive data)

Store some parameters as environment variables, to make the life a bit easier when running the commands. Replace <REPLACE ME> with the parameters of your environment:

```bash
AWS_REGION=<REPLACE ME>

# this is the SSH key name we provision the Amazon EC2 instances with, in case you want to SSH into the instance (e.g. to troubleshoot an issue)
SSH_KEY_PAIR_NAME=<REPLACE ME>

# this is the Amazon S3 bucket, where we upload the benchmark results for later analysis
S3_BUCKET_NAME=<REPLACE ME>

# these are the subnets we use to mount the EFS/FSx file systems
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
    --subnet-id $SUBNET_5_ID \
    --security-groups $SECURITY_GROUP_ID \
    | jq '.'
```

### 2.2 Create the FSx for Open ZFS file systems

We create the Amazon FSx for Open ZFS file system with `256` GB storage capacity, `4096` throughput capacity and provisioned Iops of `20000`.:
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


## 3 Build the [Amazon EC2](https://aws.amazon.com/ec2/) Amazon Machine Image (AMI), we will use for the benchmark

As base image, we use the latest Ubuntu 22.04 LTS image, available in our region.  
Beside installing some Linux utilities and Docker, we also build our Docker image, so that it's available locally in our AMI. This saves us time downloading the Docker image for each execution in a newly created EC2 instance:

```bash
UBUNTU_BASE_AMI=$(aws ec2 describe-images \
    --region $AWS_REGION \
    --output text \
    --owners amazon \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
    --query 'sort_by(Images,&CreationDate)[-1].ImageId')
echo "Ubuntu 22.04 base AMI is: $UBUNTU_BASE_AMI"

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

sudo docker images
```

You should see the container `ubuntu-yocto-image` created.

```
REPOSITORY           TAG       IMAGE ID       CREATED          SIZE
ubuntu-yocto-image   latest    3d17d924ee4d   15 minutes ago   1.12GB
ubuntu               22.04     58db3edaf2be   9 days ago       77.8MB
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


## 5 Run the cache population and benchmark for EBS

To get the benchmark baseline, run the cache provisioning and benchmark for EBS first:

```bash
rm -rf ec2-user-data-script-benchmark-ebs.txt

cat <<EOF >> ec2-user-data-script-benchmark-ebs.txt
#!/bin/bash

# Mount the EBS volume and change ownership to ubuntu
echo '### Mount the EBS volume and change ownership to ubuntu ###'
mkdir -p /workspace
file -s /dev/nvme1n1
mkfs -t xfs /dev/nvme1n1
mount /dev/nvme1n1 /workspace
mkdir -p /workspace/build /workspace/tmp /workspace/cache
chown -R ubuntu /workspace
chgrp -R ubuntu /workspace

cat <<POPULATECACHESCRIPT >> /workspace/build/populate-cache.sh
#!/bin/bash

cd /workspace
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

echo 'WARN_QA:remove = "host-user-contaminated"' >> /workspace/poky/build/conf/local.conf
echo 'DL_DIR ?= "/cache"' >> /workspace/poky/build/conf/local.conf
echo 'BB_GENERATE_MIRROR_TARBALLS = "1"' >> /workspace/poky/build/conf/local.conf
echo 'INHERIT += "own-mirrors"' >> /workspace/poky/build/conf/local.conf
echo 'SOURCE_MIRROR_URL ?= "file:////cache"' >> /workspace/poky/build/conf/local.conf

time bitbake core-image-sato-sdk --runall fetch
POPULATECACHESCRIPT


cat <<BENCHMARKEBSSCRIPT >> /workspace/build/benchmark-ebs.sh
#!/bin/bash

cd /workspace
rm -rf poky
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

echo 'WARN_QA:remove = "host-user-contaminated"' >> /workspace/poky/build/conf/local.conf
echo 'DL_DIR ?= "/cache"' >> /workspace/poky/build/conf/local.conf
echo 'BB_GENERATE_MIRROR_TARBALLS = "1"' >> /workspace/poky/build/conf/local.conf
echo 'INHERIT += "own-mirrors"' >> /workspace/poky/build/conf/local.conf
echo 'SOURCE_MIRROR_URL ?= "file:////cache"' >> /workspace/poky/build/conf/local.conf
echo 'BB_NO_NETWORK = "1"' >> /workspace/poky/build/conf/local.conf

time bitbake core-image-sato-sdk
BENCHMARKEBSSCRIPT


chmod +x /workspace/build/populate-cache.sh
chown -R ubuntu /workspace/build/populate-cache.sh
chgrp -R ubuntu /workspace/build/populate-cache.sh

chmod +x /workspace/build/benchmark-ebs.sh
chown -R ubuntu /workspace/build/benchmark-ebs.sh
chgrp -R ubuntu /workspace/build/benchmark-ebs.sh

# Running the Docker image to populate the EBS cache

echo '### Running the Docker image to populate the EFS cache ###'
sudo -u ubuntu bash -c 'cd ~; docker run --user 1000 --entrypoint /workspace/populate-cache.sh -v /workspace/build:/workspace -v /workspace/tmp:/tmp -v /workspace/cache:/cache ubuntu-yocto-image'

echo '### Running the EBS benchmark ###'
sudo -u ubuntu bash -c 'cd ~; docker run --user 1000 --entrypoint /workspace/benchmark-ebs.sh -v /workspace/build:/workspace -v /workspace/tmp:/tmp -v /workspace/cache:/cache ubuntu-yocto-image'


# Uploading the benchmark results to S3
echo '### Uploading the benchmark results to S3 ###'
EC2_INSTANCE_ID=\$(curl --silent http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r .instanceId)
EC2_AZ_ID=\$(curl --silent http://169.254.169.254/latest/meta-data/placement/availability-zone)
egrep '^real.+s$' /var/log/cloud-init-output.log | tail -1 > benchmark.txt
aws s3 cp \
    --region $AWS_REGION \
    benchmark.txt s3://$S3_BUCKET_NAME/ebs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-benchmark.txt
aws s3 cp \
    --region $AWS_REGION \
    /var/log/cloud-init-output.log s3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-cloud-init-output.log

# Uploading the sysstat metrics to S3
echo '### Uploading the sysstat metrics to S3 ###'
aws s3 cp \
    --region $AWS_REGION \
    /var/log/sysstat/* s3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID/

# Shutting down the EC2 instance, after the work is done
echo '### Shutting down the EC2 instance, after the work is done ###'
aws ec2 terminate-instances \
    --region $AWS_REGION \
    --instance-id \$EC2_INSTANCE_ID
EOF
```

When we run the benchmark, we can configure how many instances we run in parallel by changing the `count` parameter:

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
    --user-data file://ec2-user-data-script-benchmark-ebs.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Benchmark-EBS},{Key=owner,Value=cmr}]' \
    | jq '.'
```

If you want to check the progress of the benchmark, you can SSH into the instance and tail the `cloud-init-output.log` log file:

```bash
EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region $AWS_REGION \
    --filters Name=instance-state-name,Values=running \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-EBS") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')

ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_EBS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME

tail -f /var/log/cloud-init-output.log
```

To run the benchmark with an EBS io2 volume with 3000 IOPS configured (for gp3 3000 IOPS is the default), run the following command (note the ``):

```bash
aws ec2 run-instances \
    --region $AWS_REGION \
    --image-id $EC2_IMAGE_ID \
    --instance-type 'm6i.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --iam-instance-profile Arn=$EC2_INSTANCE_PROFILE_ARN \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' 'DeviceName=/dev/sdf,Ebs={VolumeSize=200,VolumeType=io2,Iops=3000,Encrypted=true}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --count 9 \
    --user-data file://ec2-user-data-script-benchmark-ebs.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Benchmark-EBS},{Key=owner,Value=cmr}]' \
    | jq '.'
```


## 6 Populate the EFS and FSx for Open ZFS file systems, running the bitbake fetch command

We are using the `core-image-sato-sdk` recipe, as it is the most demanding ready to use one.

```bash
rm -rf ec2-user-data-script-populating-cache.txt

cat <<EOF >> ec2-user-data-script-populating-cache.txt
#!/bin/bash

# Mount the EBS volume and change ownership to ubuntu
echo '### Mount the EBS volume and change ownership to ubuntu ###'
mkdir -p /workspace
file -s /dev/nvme1n1
mkfs -t xfs /dev/nvme1n1
mount /dev/nvme1n1 /workspace
mkdir -p /workspace/build /workspace/tmp
chown -R ubuntu /workspace
chgrp -R ubuntu /workspace

# Mount the EFS file system and change ownership to ubuntu
echo '### Mount the EFS file system and change ownership to ubuntu ###'
mkdir -p /cache-efs
mount -t efs $EFS_FILE_SYSTEM_ID /cache-efs
echo "$EFS_FILE_SYSTEM_ID:/ /cache-efs efs _netdev,noresvport,tls,iam 0 0" | sudo tee --append  /etc/fstab
chown -R ubuntu /cache-efs
chgrp -R ubuntu /cache-efs

# Mount the FSx file system
echo '### Mount the FSx file system ###'
mkdir -p /cache-fsx-zfs
mount -t nfs -o nfsvers=3 $FSX_FILE_SYSTEM_ID.fsx.$AWS_REGION.amazonaws.com:/fsx/ /cache-fsx-zfs
echo "$FSX_FILE_SYSTEM_ID.fsx.$AWS_REGION.amazonaws.com:/fsx/ /cache-fsx-zfs nfs nfsver=3 defaults 0 0" | sudo tee --append  /etc/fstab
# ownership from a FSx file system cannot be changed, but user ubuntu can read/write from/to it


cat <<POPULATECACHESCRIPT >> /workspace/build/populate-cache.sh
#!/bin/bash

cd /workspace
rm -rf poky
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

echo 'WARN_QA:remove = "host-user-contaminated"' >> /workspace/poky/build/conf/local.conf
echo 'DL_DIR ?= "/cache"' >> /workspace/poky/build/conf/local.conf
echo 'BB_GENERATE_MIRROR_TARBALLS = "1"' >> /workspace/poky/build/conf/local.conf
echo 'INHERIT += "own-mirrors"' >> /workspace/poky/build/conf/local.conf
echo 'SOURCE_MIRROR_URL ?= "file:////cache"' >> /workspace/poky/build/conf/local.conf

time bitbake core-image-sato-sdk --runall fetch
POPULATECACHESCRIPT


chmod +x /workspace/build/populate-cache.sh
chown -R ubuntu /workspace/build/populate-cache.sh
chgrp -R ubuntu /workspace/build/populate-cache.sh

# Running the Docker image to populate the EFS and FSx for OpenZFS cache

echo '### Running the Docker image to populate the EFS cache ###'
sudo -u ubuntu bash -c 'cd ~; docker run --user 1000 --entrypoint /workspace/populate-cache.sh -v /workspace/build:/workspace -v /workspace/tmp:/tmp -v /cache-efs:/cache ubuntu-yocto-image'

echo '### Running the Docker image to populate the FSx for OpenZFS cache ###'
sudo -u ubuntu bash -c 'cd ~; docker run --user 1000 --entrypoint /workspace/populate-cache.sh -v /workspace/build:/workspace -v /workspace/tmp:/tmp -v /cache-fsx-zfs:/cache ubuntu-yocto-image'

# Shutting down the EC2 instance, after the work is done
echo '### Shutting down the EC2 instance, after the work is done ###'
EC2_INSTANCE_ID=\$(curl --silent http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r .instanceId)
REGION=\$(curl --silent http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r .region)
aws configure set default.region \$REGION
aws ec2 terminate-instances \
    --region \$REGION \
    --instance-id \$EC2_INSTANCE_ID
EOF
```

```bash
aws ec2 run-instances \
    --region $AWS_REGION \
    --output json \
    --image-id $EC2_IMAGE_ID \
    --subnet-id $SUBNET_1_ID \
    --instance-type 'm6i.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --iam-instance-profile Arn=$EC2_INSTANCE_PROFILE_ARN \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' 'DeviceName=/dev/sdf,Ebs={VolumeSize=20,VolumeType=gp3,Encrypted=true}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --user-data file://ec2-user-data-script-populating-cache.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Benchmark-EFS-and-FSx-Population},{Key=owner,Value=cmr}]' \
    | jq '.'
```

The cache population will take around 20 minutes (around 10 minutes per file system), as we download all required dependencies for this build.
The instance will terminate automatically, once it's done.

If you want to check the progress of the cache population, you can SSH into the instance and tail the `cloud-init-output.log` log file:

```bash
EC2_EFS_FSX_CACHE_POPULATION_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region $AWS_REGION \
    --filters Name=instance-state-name,Values=running \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-EFS-and-FSx-Population") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')

ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_EFS_FSX_CACHE_POPULATION_INSTANCE_PUBLIC_DNS_NAME

tail -f /var/log/cloud-init-output.log
```

## 7 Run the benchmark with 100% cache hit for EFS

We run the benchmark and configure the build to fail, if a dependency is not cached locally to avoid measurement deviations.
First, we create the EC2 user data script which is executed when the EC2 instance is launched:

```bash
rm -rf ec2-user-data-script-benchmark-efs.txt

cat <<EOF >> ec2-user-data-script-benchmark-efs.txt
#!/bin/bash

# Mount the EBS volume and change ownership to ubuntu
echo '### Mount the EBS volume and change ownership to ubuntu ###'
mkdir -p /workspace
file -s /dev/nvme1n1
mkfs -t xfs /dev/nvme1n1
mount /dev/nvme1n1 /workspace
mkdir -p /workspace/build /workspace/tmp
chown -R ubuntu /workspace
chgrp -R ubuntu /workspace

# Mount the EFS file system and change ownership to ubuntu
echo '### Mount the EFS file system and change ownership to ubuntu ###'
mkdir -p /cache-efs
mount -t efs $EFS_FILE_SYSTEM_ID /cache-efs
echo "$EFS_FILE_SYSTEM_ID:/ /cache-efs efs _netdev,noresvport,tls,iam 0 0" | sudo tee --append  /etc/fstab
chown -R ubuntu /cache-efs
chgrp -R ubuntu /cache-efs


cat <<POPULATEEFSCACHESCRIPT >> /workspace/build/benchmark-efs.sh
#!/bin/bash

cd /workspace
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

echo 'WARN_QA:remove = "host-user-contaminated"' >> /workspace/poky/build/conf/local.conf
echo 'DL_DIR ?= "/cache"' >> /workspace/poky/build/conf/local.conf
echo 'INHERIT += "own-mirrors"' >> /workspace/poky/build/conf/local.conf
echo 'SOURCE_MIRROR_URL ?= "file:////cache"' >> /workspace/poky/build/conf/local.conf
echo 'BB_NO_NETWORK = "1"' >> /workspace/poky/build/conf/local.conf

time bitbake core-image-sato-sdk
POPULATEEFSCACHESCRIPT

chmod +x /workspace/build/benchmark-efs.sh
chown -R ubuntu /workspace/build/benchmark-efs.sh
chgrp -R ubuntu /workspace/build/benchmark-efs.sh

# Running the Docker image to benchmark EFS
echo '### Running the Docker image to benchmark EFS ###'
sudo -u ubuntu bash -c 'docker run --user 1000 --entrypoint /workspace/benchmark-efs.sh -v /workspace/build:/workspace -v /workspace/tmp:/tmp -v /cache-efs:/cache ubuntu-yocto-image'


# Uploading the benchmark results to S3
echo '### Uploading the benchmark results to S3 ###'
EC2_INSTANCE_ID=\$(curl --silent http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r .instanceId)
EC2_AZ_ID=\$(curl --silent http://169.254.169.254/latest/meta-data/placement/availability-zone)
egrep '^real.+s$' /var/log/cloud-init-output.log | tail -1 > benchmark.txt
aws s3 cp \
    --region $AWS_REGION \
    benchmark.txt s3://$S3_BUCKET_NAME/efs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-benchmark.txt
aws s3 cp \
    --region $AWS_REGION \
    /var/log/cloud-init-output.log s3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-cloud-init-output.log

# Uploading the sysstat metrics to S3
echo '### Uploading the sysstat metrics to S3 ###'
aws s3 cp \
    --region $AWS_REGION \
    /var/log/sysstat/* s3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID/

# Shutting down the EC2 instance, after the work is done
echo '### Shutting down the EC2 instance, after the work is done ###'
aws ec2 terminate-instances \
    --region $AWS_REGION \
    --instance-id \$EC2_INSTANCE_ID
EOF
```

When we start the instance, we can configure how many instances we run in parallel by changing the `count` parameter:

```bash
#    --subnet-id $SUBNET_1_ID \

aws ec2 run-instances \
    --region $AWS_REGION \
    --image-id $EC2_IMAGE_ID \
    --instance-type 'm6i.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --iam-instance-profile Arn=$EC2_INSTANCE_PROFILE_ARN \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' 'DeviceName=/dev/sdf,Ebs={VolumeSize=100,VolumeType=gp3,Encrypted=true}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --count 1 \
    --user-data file://ec2-user-data-script-benchmark-efs.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Benchmark-EFS},{Key=owner,Value=cmr}]' \
    | jq '.'
```

If you want to check the progress of a single benchmark, you can SSH into the instance and tail the `cloud-init-output.log` log file:

```bash
EC2_EFS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region $AWS_REGION \
    --filters Name=instance-state-name,Values=running \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-EFS") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')

ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_EFS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME

tail -f /var/log/cloud-init-output.log
```


## 8 Run the benchmark with 100% cache hit for FSx for Open ZFS

We run the benchmark and configure the build to fail, if a dependency is not cached locally to avoid measurement deviations.
First, we create the EC2 user data script which is executed when the EC2 instance is launched:

```bash
rm -rf ec2-user-data-script-benchmark-fsx.txt

cat <<EOF >> ec2-user-data-script-benchmark-fsx.txt
#!/bin/bash

# Mount the EBS volume and change ownership to ubuntu
echo '### Mount the EBS volume and change ownership to ubuntu ###'
mkdir -p /workspace
file -s /dev/nvme1n1
mkfs -t xfs /dev/nvme1n1
mount /dev/nvme1n1 /workspace
mkdir -p /workspace/build /workspace/tmp
chown -R ubuntu /workspace
chgrp -R ubuntu /workspace


# Mount the FSx file system
echo '### Mount the FSx file system ###'
mkdir -p /cache-fsx-zfs
mount -t nfs -o nfsvers=3,noatime,wsize=1048576,rsize=1048576,nolock $FSX_FILE_SYSTEM_ID.fsx.$AWS_REGION.amazonaws.com:/fsx /cache-fsx-zfs
echo "$FSX_FILE_SYSTEM_ID.fsx.$AWS_REGION.amazonaws.com:/fsx/ /cache-fsx-zfs nfs nfsver=3 defaults 0 0" | sudo tee --append  /etc/fstab
# ownership from a FSx file system cannot be changed, but user ubuntu can read/write from/to it


cat <<POPULATEFSXCACHESCRIPT >> /workspace/build/benchmark-fsx.sh
#!/bin/bash

cd /workspace
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

echo 'WARN_QA:remove = "host-user-contaminated"' >> /workspace/poky/build/conf/local.conf
echo 'DL_DIR ?= "/cache"' >> /workspace/poky/build/conf/local.conf
echo 'INHERIT += "own-mirrors"' >> /workspace/poky/build/conf/local.conf
echo 'SOURCE_MIRROR_URL ?= "file:////cache"' >> /workspace/poky/build/conf/local.conf
echo 'BB_NO_NETWORK = "1"' >> /workspace/poky/build/conf/local.conf

time bitbake core-image-sato-sdk
POPULATEFSXCACHESCRIPT

chmod +x /workspace/build/benchmark-fsx.sh
chown -R ubuntu /workspace/build/benchmark-fsx.sh
chgrp -R ubuntu /workspace/build/benchmark-fsx.sh

# Running the Docker image to benchmark FSx
echo '### Running the Docker image to benchmark FSx ###'
sudo -u ubuntu bash -c 'docker run --user 1000 --entrypoint /workspace/benchmark-fsx.sh -v /workspace/build:/workspace -v /workspace/tmp:/tmp -v /cache-fsx-zfs:/cache ubuntu-yocto-image'


# Uploading the benchmark results to S3
echo '### Uploading the benchmark results to S3 ###'
EC2_INSTANCE_ID=\$(curl --silent http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r .instanceId)
EC2_AZ_ID=\$(curl --silent http://169.254.169.254/latest/meta-data/placement/availability-zone)
egrep '^real.+s$' /var/log/cloud-init-output.log | tail -1 > benchmark.txt
aws s3 cp \
    --region $AWS_REGION \
    benchmark.txt s3://$S3_BUCKET_NAME/fsx/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-benchmark.txt
aws s3 cp \
    --region $AWS_REGION \
    /var/log/cloud-init-output.log s3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID-cloud-init-output.log

# Uploading the sysstat metrics to S3
echo '### Uploading the sysstat metrics to S3 ###'
aws s3 cp \
    --region $AWS_REGION \
    /var/log/sysstat/* s3://$S3_BUCKET_NAME/logs/\$EC2_INSTANCE_ID-\$EC2_AZ_ID/

# Shutting down the EC2 instance, after the work is done
echo '### Shutting down the EC2 instance, after the work is done ###'
aws ec2 terminate-instances \
    --region $AWS_REGION \
    --instance-id \$EC2_INSTANCE_ID
EOF
```

When we start the instance, we can configure how many instances we run in parallel by changing the `count` parameter:

```bash
aws ec2 run-instances \
    --region $AWS_REGION \
    --image-id $EC2_IMAGE_ID \
    --instance-type 'm6i.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --iam-instance-profile Arn=$EC2_INSTANCE_PROFILE_ARN \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' 'DeviceName=/dev/sdf,Ebs={VolumeSize=100,VolumeType=gp3,Encrypted=true}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --count 1 \
    --user-data file://ec2-user-data-script-benchmark-fsx.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Benchmark-FSx},{Key=owner,Value=cmr}]' \
    | jq '.'
```

If you want to check the progress of a single benchmark, you can SSH into the instance and tail the `cloud-init-output.log` log file:

```bash
EC2_FSX_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region $AWS_REGION \
    --filters Name=instance-state-name,Values=running \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-FSx") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')

ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_FSX_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME

tail -f /var/log/cloud-init-output.log
```


## 9 Analyse the benchmark result

After finishing the benchmark, the EC2 instance(s) will upload the measurement to the configured Amazon S3 bucket and terminate itself.
If we see all file(s) uploaded to S3, we can download and analyse them:

```bash
pip install numpy
```

To analyse the `EBS` results - our base line, run e.g.:
```bash
rm -rf tmp
mkdir -p tmp
aws s3 cp \
    --region eu-central-1 \
    --recursive \
    s3://$S3_BUCKET_NAME/ebs/gp3/1-instance tmp/

python3 analyse.py
```

To analyse the `EFS` results, run e.g.:
```bash
rm -rf tmp
mkdir -p tmp
aws s3 cp \
    --region eu-central-1 \
    --recursive \
    s3://$S3_BUCKET_NAME/efs/generalPurpose-elastic/10-instances/10.08.2023/ tmp/

python3 analyse.py
```

To analyse the `FSx` results, run:
```bash
rm -rf tmp
mkdir -p tmp
aws s3 cp \
    --region eu-central-1 \
    --recursive \
    s3://$S3_BUCKET_NAME/fsx/throughput-4096/iops-160000/10-instances/10.08.2023/ tmp/

python3 analyse.py
```

