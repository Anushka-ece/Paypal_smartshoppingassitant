import React, { useEffect, useState } from 'react';
import { ActivityIndicator, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import ChildHomeScreen from './src/screens/ChildHomeScreen';
import ParentHomeScreen from './src/screens/ParentHomeScreen';
import LoginScreen from './src/screens/LoginScreen';
import PurchaseRequestsScreen from './src/screens/PurchaseRequestsScreen';
import RulesScreen from './src/screens/RulesScreen';
import BudgetsScreen from './src/screens/BudgetsScreen';
import { apiRequest } from './src/services/api';
import { clearSession, readSession, saveSession } from './src/services/session';

export default function App() {
  const [role, setRole] = useState('parent');
  const [tab, setTab] = useState('home');
  const [transactions, setTransactions] = useState([]);
  const [budgets, setBudgets] = useState([]);
  const [token, setToken] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const [message, setMessage] = useState('Sign in to load your family data.');

  function signOut() {
    clearSession().finally(() => {
      setToken('');
      setTransactions([]);
      setTab('home');
      setMessage('Signed out. Sign in to load your family data.');
    });
  }

  async function reviewTransaction(item) {
    try {
      await apiRequest(`/transactions/${item.id}/decision`, {
        token,
        method: 'POST',
        body: JSON.stringify({ action: 'review' }),
      });
      setMessage('Transaction marked for review. PayPal payment status is unchanged.');
        await loadFamilyData(token);
    } catch (error) {
      setMessage(error.message || 'Unable to save review.');
    }
  }

    async function loadFamilyData(accessToken) {
      const [transactionResult, budgetResult] = await Promise.all([
        apiRequest('/transactions/', { token: accessToken }),
        apiRequest('/allowances/', { token: accessToken }),
      ]);
      setTransactions(transactionResult);
      setBudgets(budgetResult);
    }

  useEffect(() => {
    readSession().then((session) => {
      if (session) { setToken(session.token); setRole(session.role); }
    }).catch(() => clearSession()).finally(() => setSessionReady(true));
  }, []);

  useEffect(() => {
    let mounted = true;
    async function checkApi() {
      setLoading(true);
      try {
        if (token) {
          if (mounted) {
              await loadFamilyData(token);
            setMessage('Live family transactions loaded.');
          }
        } else {
          await apiRequest('/');
          if (mounted) setMessage('Sign in to load your family data.');
        }
      } catch (error) {
        if (mounted) setMessage(error.message || 'API is offline.');
      } finally {
        if (mounted) setLoading(false);
      }
    }
    checkApi();
    return () => { mounted = false; };
  }, [token]);

  return (
    <SafeAreaView style={styles.app}>
      {!sessionReady ? <ActivityIndicator style={styles.loader} color="#006b52" /> : !token ? <LoginScreen onLogin={(accessToken, userRole) => { saveSession(accessToken, userRole).then(() => { setToken(accessToken); setRole(userRole); }); }} /> : <>
        <View style={styles.switcher}>
          <Text style={styles.switchLabel}>{role.toUpperCase()} ACCOUNT</Text>
          <Text onPress={signOut} style={styles.signOut}>Sign out</Text>
          <Text style={styles.message}>{loading ? 'Connecting…' : message}</Text>
        </View>
        {tab === 'requests' ? <PurchaseRequestsScreen role={role} token={token} /> : tab === 'rules' && role === 'parent' ? <RulesScreen token={token} /> : tab === 'budgets' ? <BudgetsScreen role={role} token={token} /> : role === 'parent' ? <ParentHomeScreen transactions={transactions} onReview={reviewTransaction} /> : <ChildHomeScreen transactions={transactions} budgets={budgets} />}
        <View style={styles.tabs}>
          <Text onPress={() => setTab('home')} style={[styles.tab, tab === 'home' && styles.tabActive]}>Home</Text>
          <Text onPress={() => setTab('budgets')} style={[styles.tab, tab === 'budgets' && styles.tabActive]}>Budgets</Text>
          <Text onPress={() => setTab('requests')} style={[styles.tab, tab === 'requests' && styles.tabActive]}>Requests</Text>
          {role === 'parent' && <Text onPress={() => setTab('rules')} style={[styles.tab, tab === 'rules' && styles.tabActive]}>Rules</Text>}
        </View>
        {loading && <ActivityIndicator style={styles.loader} color="#006b52" />}
      </>}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  app: { flex: 1, backgroundColor: '#f6f8f6' }, switcher: { position: 'absolute', top: 0, right: 12, zIndex: 2, alignItems: 'flex-end' },
  switchLabel: { color: '#75817b', fontSize: 8, fontWeight: '700', marginBottom: 3 },
  message: { maxWidth: 230, textAlign: 'right', color: '#75817b', fontSize: 8, marginTop: 4 }, signOut: { color: '#006b52', fontSize: 9, marginTop: 4 }, loader: { position: 'absolute', bottom: 12, right: 12 },
  tabs: { position: 'absolute', bottom: 0, left: 0, right: 0, flexDirection: 'row', justifyContent: 'space-around', backgroundColor: '#fff', paddingVertical: 12, borderTopWidth: 1, borderTopColor: '#e7ece8' }, tab: { color: '#75817b', fontSize: 12, fontWeight: '600' }, tabActive: { color: '#006b52', fontWeight: '800' },
});
