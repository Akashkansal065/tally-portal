/**
 * Native Camera & Audio Recording Helpers
 *
 * Provides high-level methods for capturing photos and recording audio
 * utilizing native Capacitor plugins with web fallbacks.
 */

import { isNativePlatform } from './capacitor'

/**
 * Native Camera Options
 */
export interface NativePhotoResult {
  base64Data?: string
  dataUrl?: string
  format?: string
}

/**
 * Capture a photo using native camera if available
 */
export async function captureNativePhoto(options?: {
  quality?: number
  allowEditing?: boolean
}): Promise<NativePhotoResult | null> {
  if (!isNativePlatform()) return null

  try {
    const { Camera, CameraResultType, CameraSource } = await import('@capacitor/camera')

    // Ensure permissions
    const perm = await Camera.checkPermissions()
    if (perm.camera !== 'granted') {
      const req = await Camera.requestPermissions({ permissions: ['camera'] })
      if (req.camera !== 'granted') {
        throw new Error('Camera permission denied')
      }
    }

    const image = await Camera.getPhoto({
      quality: options?.quality ?? 85,
      allowEditing: options?.allowEditing ?? false,
      resultType: CameraResultType.Base64,
      source: CameraSource.Camera,
      correctOrientation: true,
      width: 1800,
      saveToGallery: false,
    })

    if (image.base64String) {
      return {
        base64Data: image.base64String,
        dataUrl: `data:image/${image.format || 'jpeg'};base64,${image.base64String}`,
        format: image.format,
      }
    }
    return null
  } catch (err: any) {
    console.warn('[CapacitorMedia] Native camera capture cancelled or failed:', err?.message || err)
    return null
  }
}

/**
 * Check and request voice recording permission
 */
export async function requestNativeVoicePermission(): Promise<boolean> {
  if (!isNativePlatform()) return false

  try {
    const { VoiceRecorder } = await import('capacitor-voice-recorder')
    const hasPerm = await VoiceRecorder.hasAudioRecordingPermission()
    if (hasPerm.value) return true

    const req = await VoiceRecorder.requestAudioRecordingPermission()
    return req.value
  } catch (err) {
    console.warn('[CapacitorMedia] Failed requesting audio recording permission:', err)
    return false
  }
}

/**
 * Start native voice recording
 */
export async function startNativeVoiceRecording(): Promise<boolean> {
  if (!isNativePlatform()) return false

  try {
    const { VoiceRecorder } = await import('capacitor-voice-recorder')
    const hasPerm = await requestNativeVoicePermission()
    if (!hasPerm) return false

    const result = await VoiceRecorder.startRecording()
    return result.value
  } catch (err) {
    console.warn('[CapacitorMedia] Failed starting voice recording:', err)
    return false
  }
}

/**
 * Stop native voice recording and return base64 audio data
 */
export async function stopNativeVoiceRecording(): Promise<{
  base64Audio?: string
  durationMs: number
  mimeType: string
} | null> {
  if (!isNativePlatform()) return null

  try {
    const { VoiceRecorder } = await import('capacitor-voice-recorder')
    const recording = await VoiceRecorder.stopRecording()
    if (recording && recording.value) {
      return {
        base64Audio: recording.value.recordDataBase64,
        durationMs: recording.value.msDuration,
        mimeType: recording.value.mimeType || 'audio/aac',
      }
    }
    return null
  } catch (err) {
    console.warn('[CapacitorMedia] Failed stopping voice recording:', err)
    return null
  }
}
