IMAGE_PLATFORM=linux/amd64

rm -rf build
rm -rf dist

mkdir -p dist
mkdir -p build

poetry build

cp dist/*.whl build/

cp docker/Dockerfile build/

mkdir -p build/resources
mkdir -p build/packages
mkdir -p build/submission/code/

cp dist/* build/packages/
cp -r phala/certs build/packages

cp -r tests/models_examples/bill/* build/submission/code/

cd build

echo "Building image $IMAGE_REPO_NAME:$IMAGE_TAG"
docker buildx build --platform $IMAGE_PLATFORM --no-cache -t $IMAGE_REPO_NAME:$IMAGE_TAG .