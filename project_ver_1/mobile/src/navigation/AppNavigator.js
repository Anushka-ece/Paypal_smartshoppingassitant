import React, { useState } from 'react';
import { StyleSheet, View, Text, TouchableOpacity } from 'react-native';
import HomeScreen from '../screens/HomeScreen';
import EnvelopesScreen from '../screens/EnvelopesScreen';
import PurchaseRequestScreen from '../screens/PurchaseRequestScreen';
import ReviewActionScreen from '../screens/ReviewActionScreen';
import ParentAlertModal from '../screens/ParentAlertModal';
import LoginScreen from '../screens/LoginScreen';

export default function AppNavigator() {
  const [currentTab, setCurrentTab] = useState('Home');
  const [role, setRole] = useState('PARENT');
  const [authToken, setAuthToken] = useState(null);
  const [showLogin, setShowLogin] = useState(false);
  const [alertVisible, setAlertVisible] = useState(false);
  const [activeAlert, setActiveAlert] = useState(null);

  const toggleRole = () => {
    setRole((prev) => (prev === 'PARENT' ? 'CHILD' : 'PARENT'));
  };

  const handleLogin = (token, userRole) => {
    setAuthToken(token);
    if (userRole) {
      setRole(userRole.toUpperCase());
    }
    setShowLogin(false);
  };

  const triggerTestAlert = () => {
    setActiveAlert({
      id: 999,
      merchant: 'Epic Games *Fortnite',
      amount: 49.99,
      child: 'Bart Simpson',
      flagReason: 'Rule Matched: Purchase of $49.99 exceeds the $25 gaming limit.',
      summary: 'Epic Games purchase exceeds your $25 limit.',
    });
    setAlertVisible(true);
  };

  const handleAlertAction = (action, alertData) => {
    setAlertVisible(false);
    alert(`Action ${action} executed for ${alertData.merchant}`);
  };

  if (showLogin) {
    return (
      <View style={styles.container}>
        <LoginScreen onLogin={handleLogin} />
        <TouchableOpacity style={styles.backBtn} onPress={() => setShowLogin(false)}>
          <Text style={styles.backBtnText}>← Back to App (Demo Mode)</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.screenContainer}>
        {currentTab === 'Home' && (
          <HomeScreen
            role={role}
            onSwitchRole={toggleRole}
            onTriggerAlert={triggerTestAlert}
          />
        )}
        {currentTab === 'Envelopes' && <EnvelopesScreen />}
        {currentTab === 'Request' && <PurchaseRequestScreen />}
        {currentTab === 'Review' && <ReviewActionScreen />}
      </View>

      {/* Instant Push Alert Modal for Parents */}
      <ParentAlertModal
        visible={alertVisible}
        alertData={activeAlert}
        onClose={() => setAlertVisible(false)}
        onAction={handleAlertAction}
      />

      {/* Bottom Navigation Bar */}
      <View style={styles.navBar}>
        <TouchableOpacity style={styles.navItem} onPress={() => setCurrentTab('Home')}>
          <Text style={[styles.navText, currentTab === 'Home' && styles.activeNavText]}>🏠 Home</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.navItem} onPress={() => setCurrentTab('Envelopes')}>
          <Text style={[styles.navText, currentTab === 'Envelopes' && styles.activeNavText]}>✉️ Envelopes</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.navItem} onPress={() => setCurrentTab('Request')}>
          <Text style={[styles.navText, currentTab === 'Request' && styles.activeNavText]}>🛍️ Request</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.navItem} onPress={() => setCurrentTab('Review')}>
          <Text style={[styles.navText, currentTab === 'Review' && styles.activeNavText]}>📝 Explain</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.navItem} onPress={() => setShowLogin(true)}>
          <Text style={[styles.navText, showLogin && styles.activeNavText]}>🔐 Auth</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  screenContainer: { flex: 1, paddingTop: 40 },
  backBtn: { padding: 12, alignItems: 'center', backgroundColor: '#e2e8f0' },
  backBtnText: { color: '#334155', fontWeight: '600' },
  navBar: {
    flexDirection: 'row',
    height: 60,
    backgroundColor: '#ffffff',
    borderTopWidth: 1,
    borderTopColor: '#e2e8f0',
    alignItems: 'center',
    justifyContent: 'space-around',
  },
  navItem: { alignItems: 'center', justifyContent: 'center' },
  navText: { fontSize: 13, color: '#64748b', fontWeight: '600' },
  activeNavText: { color: '#003087', fontWeight: '800' },
});
