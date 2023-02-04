# Benchmark the performance and throughput for [Amazon EFS](https://aws.amazon.com/efs) and [Amazon FSx for Open ZFS](https://aws.amazon.com/fsx/openzfs/), when running hundreds of Yocto Linux builds in parallel

Following setup is used:
- AWS Frankfurt region (eu-central-1)
- Ubuntu 22.04 LTS release as base image
- encrypted file systems with the default service KMS key, except for the instance root volume (because it doesn't contain sensitive data)


## 0 Setup

Store some parameters as environment variables, to make our life a bit easier. Replace <REPLACE ME> with the parameters of your environment:

```bash
# this is the SSH key name we provision the EC2 instances with, in case you have to SSH into it
SSH_KEY_PAIR_NAME=<REPLACE ME>

# this is the Amazon S3 bucket, where we upload the benchmark results for analysis
S3_BUCKET_NAME=<REPLACE ME>

# these are the subnets we use for EFS/FSx
SUBNET_1_ID=<REPLACE ME>
SUBNET_2_ID=<REPLACE ME>
SUBNET_3_ID=<REPLACE ME>

# the security group we use for EFS/FSx
SECURITY_GROUP_ID=<REPLACE ME>
```

## 1 Create the file systems

### 1.1 Create the EFS file systems

We create an Amazon EFS file system with `generalPurpose` performance mode and `Elastic` throughput mode. This should work best for our requirements:
```bash
aws efs create-file-system \
    --region eu-central-1 \
    --encrypted \
    --performance-mode generalPurpose \
    --throughput-mode elastic \
    --no-backup \
    --tags Key=Name,Value=Yocto-Poky-Storage-Benchmark-EFS-General-Purpose Key=owner,Value=cmr

EFS_FILE_SYSTEM_ID=$(aws efs describe-file-systems \
    --region eu-central-1 \
    --output json \
    | jq -r '.FileSystems | .[] | select(.Name == "Yocto-Poky-Storage-Benchmark-EFS-General-Purpose") | .FileSystemId')

echo "EFS file system id is: $EFS_FILE_SYSTEM_ID"

aws efs create-mount-target \
    --region eu-central-1 \
    --output json \
    --file-system-id $EFS_FILE_SYSTEM_ID \
    --subnet-id $SUBNET_1_ID \
    --security-groups $SECURITY_GROUP_ID \
    | jq '.'

aws efs create-mount-target \
    --region eu-central-1 \
    --output json \
    --file-system-id $EFS_FILE_SYSTEM_ID \
    --subnet-id $SUBNET_2_ID \
    --security-groups $SECURITY_GROUP_ID \
    | jq '.'

aws efs create-mount-target \
    --region eu-central-1 \
    --output json \
    --file-system-id $EFS_FILE_SYSTEM_ID \
    --subnet-id $SUBNET_3_ID \
    --security-groups $SECURITY_GROUP_ID \
    | jq '.'
```

### 1.1 Create the FSx for Open ZFS file systems

We create the Amazon FSx for Open ZFS file system with :
```bash
aws fsx create-file-system \
    --region eu-central-1 \
    --output json \
    --file-system-type OPENZFS \
    --storage-capacity 64 \
    --storage-type SSD \
    --subnet-ids $SUBNET_1_ID \
    --security-group-ids $SECURITY_GROUP_ID \
    --open-zfs-configuration DeploymentType=SINGLE_AZ_1,ThroughputCapacity=4096,RootVolumeConfiguration={DataCompressionType=LZ4},DiskIopsConfiguration={Mode=USER_PROVISIONED,Iops=20000} \
    --tags Key=Name,Value=Yocto-Poky-Storage-Benchmark-FSX-Open-ZFS Key=owner,Value=cmr \
    | jq '.'

FSX_FILE_SYSTEM_ID=$(aws fsx describe-file-systems \
    --region eu-central-1 \
    --output json \
    | jq -r '.FileSystems | .[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-FSX-Open-ZFS") | .FileSystemId')

echo "FSx file system id is: $FSX_FILE_SYSTEM_ID"
```


## 2 Build the [Amazon EC2](https://aws.amazon.com/ec2/) Amazon Machine Image (AMI), we will use for the benchmark

As our base image, we use `ami-03e08697c325f02ab` - the latest Ubuntu 22.04 image available as of Feb. 4th 2023.  
Beside installing some Linux utilities and Docker, we also build our Docker image, so that it's available in our AMI:

```bash
aws ec2 run-instances \
    --region eu-central-1 \
    --output json \
    --image-id 'ami-03e08697c325f02ab' \
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
    --region eu-central-1 \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-AMI") | .InstanceId')

echo "EC2 instance id is: $EC2_INSTANCE_ID"
```

The setup of this instance will take about 3 minutes, as we install required Linux utilities (see[ec2-user-data-script-provision-ec2.txt](ec2-user-data-script-provision-ec2.txt) for details).  

To verify the container creation finished, we can SSH into the EC2 instance to check:

```bash
EC2_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region eu-central-1 \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-AMI") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')

ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_INSTANCE_PUBLIC_DNS_NAME

docker images
```

You should see the container `ubuntu-yocto-image` created.

```
REPOSITORY           TAG       IMAGE ID       CREATED          SIZE
ubuntu-yocto-image   latest    3d17d924ee4d   15 minutes ago   1.12GB
ubuntu               22.04     58db3edaf2be   9 days ago       77.8MB
```

Type `exit` to leave the EC2 instance again.

After the instance is initialized, we will create the AMI based on it:
```bash
aws ec2 create-image \
    --region eu-central-1 \
    --output json \
    --instance-id $EC2_INSTANCE_ID \
    --name "Ubuntu-22.04-Yocto-Poky-Storage-Benchmark-AMI" \
    --description "Ubuntu-22.04-Yocto-Poky-Storage-Benchmark-AMI" \
    --tag-specifications 'ResourceType=image,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Benchmark-AMI},{Key=owner,Value=cmr}]' \
    --no-reboot \
    | jq -r '.'

EC2_IMAGE_ID=$(aws ec2 describe-images \
    --owners self \
    | jq -r '.Images[] | select(.Name == "Ubuntu-22.04-Yocto-Poky-Storage-Benchmark-AMI") | .ImageId')

echo "EC2 image id is: $EC2_IMAGE_ID"
```

Let's wait until the creation of this AMI finished (the CLI call will block, until the image becomes available):
```bash
aws ec2 wait image-available \
    --region eu-central-1 \
    --image-ids $EC2_IMAGE_ID
```

Afterwards, terminate the EC2 instance, as we don't need it anymore:
```bash
aws ec2 terminate-instances \
    --region eu-central-1 \
    --output json \
    --instance-id $EC2_INSTANCE_ID \
    | jq '.'
```

## 3 Populate the EFS and FSx for Open ZFS file systems, running the bitbake fetch command

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
mkdir -p /workspace/build
mkdir -p /workspace/tmp
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
mount -t nfs -o nfsvers=4.1 $FSX_FILE_SYSTEM_ID.fsx.eu-central-1.amazonaws.com:/fsx/ /cache-fsx-zfs
echo "$FSX_FILE_SYSTEM_ID.fsx.eu-central-1.amazonaws.com:/fsx/ /cache-fsx-zfs nfs nfsver=version defaults 0 0" | sudo tee --append  /etc/fstab
# ownership from a FSx file system cannot be changed, but user ubuntu can read/write from/to it


cat <<POPULATECACHESCRIPT >> /workspace/build/populate-cache.sh
#!/bin/bash

cd /workspace
rm -rf poky
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

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
EOF
```

Now we create the necessary IAM role and launch the EC2 instance, to populate our EFS and FSx file system:

```bash
aws iam create-role \
    --region eu-central-1 \
    --output json \
    --role-name EC2-Yocto-Poky-Benchmark-Role \
    --assume-role-policy-document file://trust-policy.json \
    | jq '.'

aws iam attach-role-policy \
    --region eu-central-1 \
    --output json \
    --role-name EC2-Yocto-Poky-Benchmark-Role \
    --policy-arn arn:aws:iam::aws:policy/AdministratorAccess \
    | jq '.'

aws iam create-instance-profile \
    --region eu-central-1 \
    --output json \
    --instance-profile-name storage-access-ec2-instance-profile \
    | jq '.'


EC2_INSTANCE_PROFILE_ARN=$(aws iam list-instance-profiles \
    --region eu-central-1 \
    --output json \
    | jq -r '.InstanceProfiles[] | select(.InstanceProfileName == "storage-access-ec2-instance-profile") | .Arn')

echo "EC2 instance profile ARN is: $EC2_INSTANCE_PROFILE_ARN"

aws iam add-role-to-instance-profile \
    --region eu-central-1 \
    --output json \
    --role-name EC2-Yocto-Poky-Benchmark-Role \
    --instance-profile-name storage-access-ec2-instance-profile \
    | jq '.'

aws ec2 run-instances \
    --region eu-central-1 \
    --output json \
    --image-id $EC2_IMAGE_ID \
    --instance-type 'm6i.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --iam-instance-profile Arn=$EC2_INSTANCE_PROFILE_ARN \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' 'DeviceName=/dev/sdf,Ebs={VolumeSize=20,VolumeType=gp3,Encrypted=true}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --count 1 \
    --user-data file://ec2-user-data-script-populating-cache.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Benchmark-EFS-and-FSx-Population},{Key=owner,Value=cmr}]' \
    | jq '.'
    
EC2_CACHE_POPULATION_INSTANCE_ID=$(aws ec2 describe-instances \
    --region eu-central-1 \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-EFS-and-FSx-Population") | .InstanceId')

echo "EC2 cache population image id is: $EC2_CACHE_POPULATION_INSTANCE_ID"
```

The cache population will take around 20 minutes (around 10 minutes per file system), as we download all required dependencies for this build.
To verify the cache population finished, we can SSH into the EC2 instance to check:

```bash
EC2_CACHE_POPULATION_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region eu-central-1 \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-EFS-and-FSx-Population") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')

ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_CACHE_POPULATION_INSTANCE_PUBLIC_DNS_NAME

tail -f /var/log/cloud-init-output.log
```

If you should see a similar line like below, the cache population is done. Otherwise, wait a few more minutes:

```
Cloud-init v. 22.4.2-0ubuntu0~22.04.1 finished at 
```


## 4 Run the benchmark with 100% cache hit for EFS

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
mkdir -p /workspace/build
mkdir -p /workspace/tmp
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
egrep '^real.+s$' /var/log/cloud-init-output.log > benchmark.txt
aws s3 cp \
    --region eu-central-1 \
    benchmark.txt s3://$S3_BUCKET_NAME/efs/\$EC2_INSTANCE_ID-benchmark.txt


# Shutting down the EC2 instance, after the work is done
echo '### Shutting down the EC2 instance, after the work is done ###'
aws ec2 terminate-instances \
    --region eu-central-1 \
    --instance-id \$EC2_INSTANCE_ID
EOF
```

When we start the instance, we can configure how many instances we run in parallel by changing the `count` parameter:

```bash
aws ec2 run-instances \
    --region eu-central-1 \
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

```
EC2_EFS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region eu-central-1 \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-EFS") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')

ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_EFS_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME

tail -f /var/log/cloud-init-output.log
```


## 5 Run the benchmark with 100% cache hit for FSx for Open ZFS

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
mkdir -p /workspace/build
mkdir -p /workspace/tmp
chown -R ubuntu /workspace
chgrp -R ubuntu /workspace


# Mount the FSx file system
echo '### Mount the FSx file system ###'
mkdir -p /cache-fsx-zfs
mount -t nfs -o nfsvers=4.1 $FSX_FILE_SYSTEM_ID.fsx.eu-central-1.amazonaws.com:/fsx/ /cache-fsx-zfs
echo "$FSX_FILE_SYSTEM_ID.fsx.eu-central-1.amazonaws.com:/fsx/ /cache-fsx-zfs nfs nfsver=version defaults 0 0" | sudo tee --append  /etc/fstab
# ownership from a FSx file system cannot be changed, but user ubuntu can read/write from/to it


cat <<POPULATEFSXCACHESCRIPT >> /workspace/build/benchmark-fsx.sh
#!/bin/bash

cd /workspace
git clone --depth 1 --branch kirkstone git://git.yoctoproject.org/poky
cd poky
source oe-init-build-env

echo 'DL_DIR ?= "/cache"' >> /workspace/poky/build/conf/local.conf
echo 'INHERIT += "own-mirrors"' >> /workspace/poky/build/conf/local.conf
echo 'SOURCE_MIRROR_URL ?= "file:////cache"' >> /workspace/poky/build/conf/local.conf
echo 'BB_NO_NETWORK = "1"' >> /workspace/poky/build/conf/local.conf

time bitbake core-image-minimal
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
egrep '^real.+s$' /var/log/cloud-init-output.log > benchmark.txt
aws s3 cp \
    --region eu-central-1 \
    benchmark.txt s3://$S3_BUCKET_NAME/fsx/\$EC2_INSTANCE_ID-benchmark.txt


# Shutting down the EC2 instance, after the work is done
echo '### Shutting down the EC2 instance, after the work is done ###'
aws ec2 terminate-instances \
    --region eu-central-1 \
    --instance-id \$EC2_INSTANCE_ID
EOF
```

When we start the instance, we can configure how many instances we run in parallel by changing the `count` parameter:

```bash
aws ec2 run-instances \
    --region eu-central-1 \
    --image-id $EC2_IMAGE_ID \
    --instance-type 'm6i.4xlarge' \
    --key-name $SSH_KEY_PAIR_NAME \
    --iam-instance-profile Arn=$EC2_INSTANCE_PROFILE_ARN \
    --ebs-optimized \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' 'DeviceName=/dev/sdf,Ebs={VolumeSize=100,VolumeType=gp3,Encrypted=true}' \
    --instance-initiated-shutdown-behavior 'terminate' \
    --count 1 \
    --user-data file://ec2-user-data-script-benchmark-efs.txt \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Yocto-Poky-Storage-Benchmark-FSx},{Key=owner,Value=cmr}]' \
    | jq '.'
```

If you want to check the progress of a single benchmark, you can SSH into the instance and tail the `cloud-init-output.log` log file:

```
EC2_FSX_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME=$(aws ec2 describe-instances \
    --region eu-central-1 \
    --output json \
    | jq -r '.Reservations | .[].Instances[] | select(.Tags[].Value == "Yocto-Poky-Storage-Benchmark-FSx") | .NetworkInterfaces[0].PrivateIpAddresses[0].Association.PublicDnsName')

ssh -o "ServerAliveInterval 60" -i "~/$SSH_KEY_PAIR_NAME.pem" ubuntu@$EC2_FSX_BENCHMARK_INSTANCE_PUBLIC_DNS_NAME

tail -f /var/log/cloud-init-output.log
```

## 6 Analyse the benchmark result

After finishing the benchmark, the EC2 instance(s) will upload the measurement to the configured Amazon S3 bucket and terminate itself.
If we see all file(s) uploaded to S3, we can download and analyse them:

```bash
rm -rf tmp
mkdir -p tmp
aws s3 cp \
    --region eu-central-1 \
    --recursive \
    s3://$S3_BUCKET_NAME/efs/ tmp/

python3 analyse.py
```
EFS
1 Instance (with Bursting performance settings):
min: 38m 16s
max: 38m 30s
avg: 38m 30s, 38m 16s, 38m 6s, 38m 51s, 38m 7s, 37m 35s, 

10 Instances (with Bursting performance settings):
min: 37m 37s
max: 39m 14s
avg: 38m 34s

50 Instances (with Bursting performance settings):
min: 37m 30s
max: 46m 58s
avg: 41m 1s

100 Instances (with Bursting performance settings):
min: 38m 26s
max: 56m 6s
avg: 47m 23s

200 Instances (with Bursting performance settings):
min: 48m 47s
max: 91m 34s
avg: 75m 11s

200 Instances (with Enhanced performance settings & Elastic IOPS provisioning):
min: 48m 49s
max: 93m 10s
avg: 76m 29s


---

FSX

--> IOPS von 192 -> xxxx

1 Instance (with 192 IOPS):
min: 38m 29s
max: 38m 31s
avg: 38m 29s, 38m 31s, 38m 20s, 38m 23s, 38m 22s, 37m 42s, 

10 Instances (with 192 IOPS):
min: 37m 56s
max: 39m 32s
avg: 38m 30s

50 Instances (with 192 IOPS):
min: 38m 0s
max: 45m 22s
avg: 40m 17s

100 Instances (with 192 IOPS):
min: 38m 9s
max: 56m 58s
avg: 45m 16s

200 Instances (with 192 IOPS):
min: 38m 14s
max: 121m 32s
avg: 89m 35s

200 Instances (with 10.000 IOPS):
min: 38m 4s
max: 76m 23s
avg: 56m 2s

```bash
less /var/log/cloud-init-output.log
less /var/log/cloud-init.log
```
