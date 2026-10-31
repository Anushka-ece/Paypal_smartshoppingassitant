import React, { useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { apiRequest } from '../services/api';

export default function LoginScreen({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit() {
    setError('');
    setLoading(true);
    try {
      const result = await apiRequest('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
      onLogin(result.access_token, result.role);
    } catch (exception) {
      setError(exception.message || 'Unable to sign in.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.page}>
      <Text style={styles.brand}>PennyPilot</Text>
      <Text style={styles.title}>Money habits, together.</Text>
      <Text style={styles.subtitle}>Sign in to your family account.</Text>
      <TextInput autoCapitalize="none" keyboardType="email-address" placeholder="Email address" value={email} onChangeText={setEmail} style={styles.input} />
      <TextInput secureTextEntry placeholder="Password" value={password} onChangeText={setPassword} style={styles.input} />
      {!!error && <Text style={styles.error}>{error}</Text>}
      <TouchableOpacity onPress={submit} disabled={loading} style={styles.button}>
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Sign in</Text>}
      </TouchableOpacity>
      <Text style={styles.footnote}>Use your parent account to securely manage family budgets and approvals.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, justifyContent: 'center', padding: 26, backgroundColor: '#f6f8f6' }, brand: { color: '#006b52', fontSize: 17, fontWeight: '800', marginBottom: 34 },
  title: { color: '#17231e', fontSize: 28, fontWeight: '800' }, subtitle: { color: '#75817b', marginTop: 8, marginBottom: 25 }, input: { padding: 14, backgroundColor: '#fff', borderColor: '#e7ece8', borderWidth: 1, borderRadius: 12, marginBottom: 11, color: '#17231e' },
  button: { backgroundColor: '#006b52', padding: 15, borderRadius: 12, alignItems: 'center', marginTop: 5 }, buttonText: { color: '#fff', fontWeight: '700' }, error: { color: '#b64040', fontSize: 12, marginBottom: 8 }, footnote: { color: '#75817b', fontSize: 11, lineHeight: 17, marginTop: 18 },
});
