# Benchmark the performance and throughput for [Amazon EBS](https://aws.amazon.com/ebs/), [Amazon EFS](https://aws.amazon.com/efs) and [Amazon FSx for Open ZFS](https://aws.amazon.com/fsx/openzfs/), when running hundreds of Yocto Linux builds in parallel

## 1 Results

### 1.1 Amazon EBS

![benchmark-EBS-set-up.png](images%2Fbenchmark-EBS-set-up.png)

|           | 1 instance                                                                                      | 10 instances | 100 instances | 200 instances                                                                                    |
|-----------|-------------------------------------------------------------------------------------------------|--------------|---------------|--------------------------------------------------------------------------------------------------|
| EBS (gp3) | P0: 97m 42s<br>P50: 99m 35s<br>P75: 99m 48s<br>P90: 101m 17s<br>P98: 101m 37s<br>P100: 101m 42s | -            | -             | P0: 97m 24s<br>P50: 99m 33s<br>P75: 101m 16s<br>P90: 102m 50s<br>P98: 106m 02s<br>P100: 112m 33s |
| EBS (io2) | P0: 97m 48s<br>P50: 98m 38s<br>P75: 99m 59s<br>P90: 105m 18s<br>P98: 105m 58s<br>P100: 106m 08s | -            | -             | -                                                                                                |


### 1.2 Amazon EFS

![benchmark-EFS-set-up.png](images%2Fbenchmark-EFS-set-up.png)

|                                                                            | 1 instance                                                                                   | 10 instances                                                                                     | 50 instances                                                                                      | 100 instances                                                                                    | 200 instances                                                                                      |
|----------------------------------------------------------------------------|----------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| 05.02.2023: EFS (performance mode generalPurpose; throughput mode elastic) | P0: 98m 27s<br>P50: 98m 41s<br>P75: 98m 48s<br>P90: 98m 52s<br>P98: 98m 54s<br>P100: 98m 55s | P0: 98m 11s<br>P50: 98m 49s<br>P75: 100m 00s<br>P90: 101m 13s<br>P98: 101m 29s<br>P100: 101m 33s | P0: 98m 57s<br>P50: 103m 30s<br>P75: 105m 33s<br>P90: 109m 33s<br>P98: 119m 12s<br>P100: 119m 41s | P0: 97m 53s<br>P50: 117m 06s<br>P75: 127m 22s<br>P90: 135m 59s<br>P98: 142m 36s<br>P100: 143m 58s | P0: 104m 34s<br>P50: 170m 45s<br>P75: 184m 57s<br>P90: 197m 21s<br>P98: 207m 26s<br>P100: 211m 24s |
| 07.05.2023: EFS (performance mode generalPurpose; throughput mode elastic) |                                                                                              | P0: 96m 54s<br>P50: 97m 54s<br>P75: 98m 57s<br>P90: 99m 12s<br>P98: 100m 03s<br>P100: 100m 16s   | P0: 97m 08s<br>P50: 101m 58s<br>P75: 104m 28s<br>P90: 112m 00s<br>P98: 115m 04s<br>P100: 115m 20s | P0: 98m 11s<br>P50: 114m 45s<br>P75: 130m 04s<br>P90: 136m 37s<br>P98: 141m 56s<br>P100: 143m 38s | P0: 101m 43s<br>P50: 157m 07s<br>P75: 171m 41s<br>P90: 185m 50s<br>P98: 194m 02s<br>P100: 198m 05s |
| 10.08.2023: EFS (performance mode generalPurpose; throughput mode elastic) | P0: 98m 30s<br><br><br><br><br>                                                              | P0: 97m 09s<br>P50: 99m 54s<br>P75: 100m 15s<br>P90: 100m 53s<br>P98: 101m 17s<br>P100: 101m 23s | P0: 97m 01s<br>P50: 101m 19s<br>P75: 102m 24s<br>P90: 105m 15s<br>P98: 111m 07s<br>P100: 112m 00s | P0: 97m 34s<br>P50: 112m 02s<br>P75: 118m 36s<br>P90: 129m 08s<br>P98: 135m 52s<br>P100: 138m 25s | <br><br><br><br><br>                                                                               |

![efs-200-instances-generalPurpose-elastic-iops.png](images%2Fefs-200-instances-generalPurpose-elastic-iops.png)

![efs-200-instances-generalPurpose-elastic-throughput.png](images%2Fefs-200-instances-generalPurpose-elastic-throughput.png)


|                                                                               | 1 instance                                                                                      | 10 instances                                                                                     | 50 instances                                                                                      | 100 instances                                                                                     | 200 instances                                                                                     |
|-------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| EFS (performance mode generalPurpose; throughput mode provisioned 1024 MiB/s) | P0: 99m 33s<br>P50: 99m 50s<br>P75: 99m 59s<br>P90: 100m 04s<br>P98: 100m 07s<br>P100: 100m 08s | P0: 98m 31s<br>P50: 99m 55s<br>P75: 100m 18s<br>P90: 101m 06s<br>P98: 102m 16s<br>P100: 102m 34s | P0: 97m 56s<br>P50: 103m 39s<br>P75: 105m 57s<br>P90: 113m 15s<br>P98: 118m 33s<br>P100: 119m 09s | P0: 98m 00s<br>P50: 117m 57s<br>P75: 127m 41s<br>P90: 137m 47s<br>P98: 143m 17s<br>P100: 145m 21s | P0: 98m 00s<br>P50: 117m 57s<br>P75: 127m 41s<br>P90: 137m 47s<br>P98: 143m 17s<br>P100: 145m 21s |


![efs-200-instances-generalPurpose-provisioned-1024-iops.png](images%2Fefs-200-instances-generalPurpose-provisioned-1024-iops.png)

![efs-200-instances-generalPurpose-provisioned-1024-throughput.png](images%2Fefs-200-instances-generalPurpose-provisioned-1024-throughput.png)


|                                                                 | 1 instance                                                                                   | 10 instances                                                                                     | 50 instances                                                                                     | 100 instances                                                                                     | 200 instances                                                                                      |
|-----------------------------------------------------------------|----------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| EFS (performance mode generalPurpose; throughput mode bursting) | P0: 99m 12s<br>P50: 99m 12s<br>P75: 99m 12s<br>P90: 99m 12s<br>P98: 99m 12s<br>P100: 99m 12s | P0: 97m 55s<br>P50: 99m 26s<br>P75: 100m 03s<br>P90: 101m 38s<br>P98: 102m 57s<br>P100: 103m 42s | P0: 99m 19s<br>P50: 103m 18s<br>P75: 104m 51s<br>P90: 108m 09s<br>P98: 114m 44s<br>P100: 117m 13 | P0: 97m 25s<br>P50: 119m 58s<br>P75: 130m 06s<br>P90: 136m 38s<br>P98: 146m 08s<br>P100: 152m 43s | P0: 103m 06s<br>P50: 162m 14s<br>P75: 177m 21s<br>P90: 190m 42s<br>P98: 199m 49s<br>P100: 204m 01s |

![efs-200-instances-generalPurpose-bursting-iops.png](images%2Fefs-200-instances-generalPurpose-bursting-iops.png)

![efs-200-instances-generalPurpose-bursting-throughput.png](images%2Fefs-200-instances-generalPurpose-bursting-throughput.png)

|                                                                               | 1 instance | 10 instances | 100 instances | 200 instances |
|-------------------------------------------------------------------------------|------------|--------------|---------------|---------------|
| EFS (performance mode maxIO; throughput mode elastic)                         |            |              |               |               |
| EFS (performance mode maxIO; throughput mode bursting)                        |            |              |               |               |
| EFS (performance mode maxIO; throughput mode provisioned 1024 MiB/s)          |            |              |               |               |


### 1.3 Amazon FSx for OpenZFS

![benchmark-FSx-set-up.png](images%2Fbenchmark-FSx-set-up.png)

|                                                                                                                                            | 1 instance                                                                                         | 10 instances                                                                                     | 50 instances                                                                                      | 100 instances                                                                                      | 200 instances                                                                                      |
|--------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| FSx (storage-capacity: 282 GB; throughput capacity: 4096; user provisioned Iops: 20000)                                                    | P0: 99m 27s<br>P50: 99m 27s<br>P75: 99m 27s<br>P90: 99m 27s<br>P98: 99m 27s<br>P100: 99m 27s       | P0: 97m 30s<br>P50: 99m 33s<br>P75: 100m 24s<br>P90: 101m 10s<br>P98: 101m 56s<br>P100: 102m 08s | P0: 99m 15s<br>P50: 104m 55s<br>P75: 107m 54s<br>P90: 117m 28s<br>P98: 129m 03s<br>P100: 129m 04s | P0: 101m 30s<br>P50: 139m 09s<br>P75: 149m 36s<br>P90: 160m 03s<br>P98: 164m 43s<br>P100: 167m 40s | P0: 125m 10s<br>P50: 201m 31s<br>P75: 219m 41s<br>P90: 229m 53s<br>P98: 240m 06s<br>P100: 253m 06s |
| FSx (storage-capacity: 256 GB; throughput capacity: 4096; user provisioned Iops: 20000) - all instances & FSx in same AZ                   | P0: 100m 03s<br>P50: 100m 03s<br>P75: 100m 03s<br>P90: 100m 03s<br>P98: 100m 03s<br>P100: 100m 03s | P0: 98m 43s<br>P50: 99m 23s<br>P75: 100m 23s<br>P90: 101m 45s<br>P98: 101m 52s<br>P100: 101m 54s | P0: 97m 40s<br>P50: 103m 41s<br>P75: 106m 51s<br>P90: 111m 27s<br>P98: 123m 44s<br>P100: 124m 27s | <br><br><br><br><br>                                                                               | P0: 114m 18s<br>P50: 206m 41s<br>P75: 226m 48s<br>P90: 241m 40s<br>P98: 254m 29s<br>P100: 263m 53s |
| FSx (storage-capacity: 1024 GB; throughput capacity: 4096; user provisioned Iops: 20000) - all instances & FSx in same AZ                  | <br><br><br><br><br>                                                                               | <br><br><br><br><br>                                                                             | <br><br><br><br><br>                                                                              | <br><br><br><br><br>                                                                               | P0: 116m 55s<br>P50: 184m 26s<br>P75: 199m 08s<br>P90: 213m 37s<br>P98: 221m 16s<br>P100: 229m 05s |
| FSx (storage-capacity: 1024 GB; throughput capacity: 4096; user provisioned Iops: 20000) - 2 times 100 instances in 2 AZs - same AZ as FSx | <br><br><br><br><br>                                                                               | <br><br><br><br><br>                                                                             | <br><br><br><br><br>                                                                              | <br><br><br><br><br>                                                                               | P0: 97m 55s<br>P50: 128m 15s<br>P75: 140m 18s<br>P90: 151m 54s<br>P98: 164m 02s<br>P100: 174m 54s  |
| FSx (storage-capacity: 1024 GB; throughput capacity: 4096; user provisioned Iops: 160000)                                                  | P0: 99m 50s<br><br><br><br><br>                                                                    | P0: 95m 37s<br>P50: 96m 27s<br>P75: 97m 44s<br>P90: 98m 02s<br>P98: 98m 47s<br>P100: 98m 59s     | P0: 95m 49s<br>P50: 97m 12s<br>P75: 98m 49s<br>P90: 100m 27s<br>P98: 103m 00s<br>P100: 113m 59s   | P0: 95m 25s<br>P50: 97m 26s<br>P75: 99m 28s<br>P90: 101m 51s<br>P98: 105m 01s<br>P100: 111m 38s    | <br><br><br><br><br>                                                                               |

![fsx-zfs-200-instances-282-capacity-4096-throughput-20000-iops-iops.png](images%2Ffsx-zfs-200-instances-282-capacity-4096-throughput-20000-iops-iops.png)

![fsx-zfs-200-instances-282-capacity-4096-throughput-20000-iops-throughput.png](images%2Ffsx-zfs-200-instances-282-capacity-4096-throughput-20000-iops-throughput.png)

![fsx-zfs-200-instances-282-capacity-4096-throughput-20000-iops-utilisation.png](images%2Ffsx-zfs-200-instances-282-capacity-4096-throughput-20000-iops-utilisation.png)

