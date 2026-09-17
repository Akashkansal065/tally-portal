export const getCroppedImg = async (
  imageSrc: string,
  pixelCrop: { x: number; y: number; width: number; height: number },
  rotation = 0
): Promise<string> => {
  const image = await new Promise<HTMLImageElement>((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = (error) => reject(error)
    img.src = imageSrc
  })

  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')

  if (!ctx) {
    return ''
  }

  // Calculate bounding box of the rotated image
  const safeArea = Math.max(image.width, image.height) * 2
  
  canvas.width = safeArea
  canvas.height = safeArea

  // Translate canvas context to a central location to allow rotating around the center.
  ctx.translate(safeArea / 2, safeArea / 2)
  ctx.rotate((rotation * Math.PI) / 180)
  ctx.translate(-safeArea / 2, -safeArea / 2)

  // Draw the image in the center of the canvas
  ctx.drawImage(
    image,
    safeArea / 2 - image.width / 2,
    safeArea / 2 - image.height / 2
  )

  // Extract the cropped image
  const data = ctx.getImageData(
    safeArea / 2 - image.width / 2 + pixelCrop.x,
    safeArea / 2 - image.height / 2 + pixelCrop.y,
    pixelCrop.width,
    pixelCrop.height
  )

  // Set canvas width/height to crop size
  canvas.width = pixelCrop.width
  canvas.height = pixelCrop.height

  // Paste the extracted image data
  ctx.putImageData(data, 0, 0)

  return canvas.toDataURL('image/jpeg', 0.9)
}
