import time


class ROM:
    """
    Non-Intrusive Reduced Order Modeling Class

    ...

    Parameters
    ----------
    rom_object : python class
        an instance of a class that represents a method for reduced
        order modeling it has to have the methods decompose(),
        reconstruct() and predict()

        The class' decompose() method must take as arguments at least
        the same arguments of ROM.decompose(), same thing for
        ROM.reconstruct() and ROM.predict()

    """

    def __init__(self, rom_object):

        self.model = rom_object
        self.snapshots = None

        self.singvals = None
        self.modes = None
        self.time = None
        self.profile = {}

    def decompose(
            self,
            X,
            center=False,
            alg="svd",
            rank=0,
            opt_trunc=False,
            tikhonov=0,
            *args,
            **kwargs,):
        """Computes the data decomposition, training the model on the input data X.
                                            (SVD - based)

        Parameters
        ----------
        X : numpy.ndarray
            Snapshot matrix data, of (N, m) size 
        center : bool, optional
            Flag to either center the data around time or not
            Default : False
        alg : str, optional
            Whether to use the SVD on decomposition ("svd") or
            the eigenvalue problem on snaphot matrices ("snap")
            Default : "svd"
        rank : int or float, optional
            if rank = 0 All the ranks are kept, unless their
            singular values are zero
            if 0 < rank < 1, it is used as the percentage of
            the energy that should be kept, and the rank is
            computed accordingly
            Default : 0
        opt_trunc : bool, optional
            if True an optimal truncation/threshold is estimated,
            based on the algorithm of Gavish and Donoho [1]
            Default : False
        tikhonov : int or float, optional
            tikhonov parameter for regularization
            If 0, no regularization is applied, if float, it is used as
            the lambda tikhonov parameter
            Default : 0

        References
        ----------

        [1] On dynamic mode decomposition:  Theory and applications,
        Journal of Computational Dynamics,1,2,391,421,2014-12-1,
        Jonathan H. Tu,Clarence W. Rowley,Dirk M. Luchtenburg,
        Steven L. Brunton,J. Nathan Kutz,2158-2491_2014_2_391,



        """

        self.snapshots = X.copy()

        t0 = time.time()
        u, s, vh = self.model.decompose(X=self.snapshots,
                                        center=center,
                                        alg=alg,
                                        rank=rank,
                                        opt_trunc=opt_trunc,
                                        tikhonov=tikhonov,
                                        *args,
                                        **kwargs,)

        self.singvals = s
        self.modes = u
        self.time = vh
        t1 = time.time()

        self.profile["Training time"] = t1-t0

    def predict(self, t, t1=0, rank=None, *args, **kwargs):
        """Predict the solution of the reduced order model on the prescribed time instants.

        Parameters
        ----------
        t : numpy.ndarray, size (nt, )
            time steps at which the ROM solution will be computed
        t1: float
            the value of the time instant of the first snapshot
        rank: int or None
            ranks kept for prediction: it should be a hard threshold integer
            and greater than the rank chose/computed in the decomposition
            phase. If None, the same rank already computed is used
            Default : None 

        Returns
        ----------
            numpy.ndarray, size (N, nt)
            ROM solution on the time values t
        """
        t0 = time.time()
        res = self.model.predict(t=t, t1=t1, rank=rank, *args, **kwargs)
        t1 = time.time()
        self.profile["Prediction time"] = t1-t0
        return res

    def reconstruct(self, rank=None):
        """Reconstruct the data input using the Reduced Order Model.

        Parameters
        ----------
        rank: int or None
            ranks kept for prediction: it should be a hard threshold integer
            and greater than the rank chose/computed in the decomposition
            phase. If None, the same rank already computed is used
            Default : None 

        Returns
        ----------
            numpy.ndarray, size (N, m)
            ROM solution on the time steps where the input snapshots are taken
        """
        return self.model.reconstruct(rank=rank)
