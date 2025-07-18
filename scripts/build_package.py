import os
import subprocess

import boto3


def run():
    """Automates the Poetry build process and uploads artifacts to S3."""
    print("Building the package with Poetry...")
    result = subprocess.run(["poetry", "build"], capture_output=True, text=True)

    if result.returncode == 0:
        print("Build successful! Uploading artifacts to S3...")

        # Configure S3
        bucket_name = "crunchdao--model-runner"
        s3_client = boto3.client("s3")

        # TODO manage multiple version or use python repository to prevent that
        dist_dir = os.path.join(os.getcwd(), "dist")
        for artifact in os.listdir(dist_dir):
            artifact_path = os.path.join(dist_dir, artifact)
            s3_key = f"packages/{artifact}"
            s3_client.upload_file(artifact_path, bucket_name, s3_key)
            print(f"Uploaded: {artifact} -> s3://{bucket_name}/{s3_key}")

        # upload docker files
        docker_dir = os.path.join(os.getcwd(), "docker")
        artifact_path = os.path.join(docker_dir, "Dockerfile")
        artifact = "Dockerfile"
        s3_key = artifact
        s3_client.upload_file(artifact_path, bucket_name, "Dockerfile")
        print(f"Uploaded: {artifact} -> s3://{bucket_name}/{s3_key}")

    else:
        print("Build failed!")
        print(result.stderr)


if __name__ == "__main__":
    run()
