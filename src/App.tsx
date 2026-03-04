import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { Optimize } from './pages/Optimize';
import { History } from './pages/History';
import { Settings } from './pages/Settings';
import { useStore } from './stores/useStore';
import './index.css';

function App() {
  const { currentPage } = useStore();

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard />;
      case 'optimize':
        return <Optimize />;
      case 'history':
        return <History />;
      case 'settings':
        return <Settings />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <Layout>
      {renderPage()}
    </Layout>
  );
}

export default App;
