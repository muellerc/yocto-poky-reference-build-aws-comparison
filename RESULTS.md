# Benchmark the performance and throughput for [Amazon EBS](https://aws.amazon.com/ebs/), [Amazon EFS](https://aws.amazon.com/efs) and [Amazon FSx for Open ZFS](https://aws.amazon.com/fsx/openzfs/), when running hundreds of Yocto Linux builds in parallel

## 1 Results

### 1.1 Amazon EBS

![benchmark-EBS-set-up.png](images%2Fbenchmark-EBS-set-up.png)

|                                          | 1 instance                      | 10 instances | 100 instances | 200 instances |
|------------------------------------------|---------------------------------|--------------|---------------|---------------|
| type: gp3<br>IOPS: 60<br>Throughput: 125 | P0: 96m 12s<br><br><br><br><br> | -            | -             | -             |


### 1.2 Amazon EFS

![benchmark-EFS-set-up.png](images%2Fbenchmark-EFS-set-up.png)


|                                                              | 1 instance           | 10 instances         | 100 instances        | 200 instances        |
|--------------------------------------------------------------|----------------------|----------------------|----------------------|----------------------|
| performance mode: generalPurpose<br>throughput mode: elastic | <br><br><br><br><br> | <br><br><br><br><br> | <br><br><br><br><br> | <br><br><br><br><br> |


### 1.3 Amazon FSx for OpenZFS

![benchmark-FSx-set-up.png](images%2Fbenchmark-FSx-set-up.png)


|                                                                                                                | 1 instance                     | 10 instances         | 50 instances         | 100 instances        | 200 instances        |
|----------------------------------------------------------------------------------------------------------------|--------------------------------|----------------------|----------------------|----------------------|----------------------|
| storage-capacity: 1024 GB<br>throughput capacity: 4096<br>user provisioned Iops: 20000<br>all in same AZ: true | P0: 96m 1s<br><br><br><br><br> | <br><br><br><br><br> | <br><br><br><br><br> | <br><br><br><br><br> | <br><br><br><br><br> |


### 1.4 Amazon S3 (Standard) Mountpoint

|             | 1 instance      | 10 instances | 50 instances | 100 instances | 200 instances |
|-------------|-----------------|--------------|--------------|---------------|---------------|
| S3 Standard | P0: 96m 53s<br> |              |              |               |               |


### 1.5 Amazon S3 (Express) Mountpoint

|            | 1 instance      | 10 instances | 50 instances | 100 instances | 200 instances |
|------------|-----------------|--------------|--------------|---------------|---------------|
| S3 Express | P0: 96m 13s<br> |              |              |               |               |
