import * as SecureStore from 'expo-secure-store';

const SESSION_KEY = 'pennypilot_session_v1';

export async function saveSession(token, role) {
  await SecureStore.setItemAsync(SESSION_KEY, JSON.stringify({ token, role }));
}

export async function readSession() {
  const stored = await SecureStore.getItemAsync(SESSION_KEY);
  return stored ? JSON.parse(stored) : null;
}

export async function clearSession() {
  await SecureStore.deleteItemAsync(SESSION_KEY);
}
